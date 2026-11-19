# novel_generator/codex_adapter.py
# -*- coding: utf-8 -*-
"""
基于本地 OpenAI Codex CLI 的大模型适配器。
直接复用本地已登录的 Codex 环境与 GPT 模型，完全免密调用。
"""

import os
import sys
import shutil
import subprocess
import tempfile
import logging
from typing import Optional, Generator

logger = logging.getLogger("CodexAdapter")


class CodexCLIAdapter:
    """
    OpenAI Codex 本地 CLI 适配器。
    使用 `codex exec` 进行非交互式任务执行，支持管道长文本输入及输出精准提取。
    """

    def __init__(self, model_name: Optional[str] = None, timeout: int = 300):
        self.model_name = (model_name or "").strip()
        self.timeout = timeout
        self.codex_path = self._find_codex()
        if not self.codex_path:
            logger.warning("[CodexAdapter] 未在系统中找到 codex 可执行文件，请确认已安装 Codex CLI")

    @classmethod
    def _find_codex(cls) -> Optional[str]:
        """寻找本地可用的 codex 可执行文件"""
        # 1. 检查环境变量 PATH
        p = shutil.which("codex")
        if p and os.path.exists(p):
            return p

        # 2. 检查 AppData 下的 OpenAI Codex 常见安装路径
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            base_dir = os.path.join(local_app, "OpenAI", "Codex", "bin")
            if os.path.isdir(base_dir):
                for root, _, files in os.walk(base_dir):
                    if "codex.exe" in files:
                        target = os.path.join(root, "codex.exe")
                        if os.path.exists(target):
                            return target

            win_apps = os.path.join(local_app, "Microsoft", "WindowsApps", "codex.exe")
            if os.path.exists(win_apps):
                return win_apps

        return None

    def is_available(self) -> bool:
        """检查 Codex CLI 是否可用"""
        return bool(self.codex_path and os.path.exists(self.codex_path))

    def invoke(self, prompt: str, system_message: str = "", model: Optional[str] = None) -> str:
        """
        同步调用 Codex CLI 生成结果。
        通过 --output-last-message 将最终纯净回答写入临时文件，规避控制台日志杂音。
        """
        if not self.is_available():
            raise RuntimeError(f"Codex CLI 未找到，无法执行调用。路径: {self.codex_path}")

        chosen_model = (model or self.model_name or "").strip()

        # 拼装提示词与防破壁指令
        core_instruction = (
            "【系统最高核心指令】：你是一位拥有二十年小说出版经验的资深网文总编辑。\n"
            "你的任务是彻底清除文本中的 AI 痕迹、陈词滥调、假大空排比和翻译腔，重塑真实、有颗粒感、生活化与电影镜头感的自然文学质感。\n"
            "严禁执行任何代码审查、严禁调用任何终端工具、严禁创建或修改磁盘文件，必须直接输出纯文本小说改写结果与修改清单。\n\n"
        )
        full_prompt = f"{core_instruction}{system_message}\n\n{prompt}" if system_message else f"{core_instruction}{prompt}"

        # 准备临时输出文件
        temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", prefix="codex_out_")
        temp_out_path = temp_out.name
        temp_out.close()

        cmd = [
            self.codex_path,
            "exec",
            "--sandbox", "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "-o", temp_out_path,
        ]

        # 如果指定了有效模型名且非自动/默认，则添加 -m 参数
        if chosen_model and chosen_model.lower() not in ("default", "auto", "codex", "本地模型", "系统默认"):
            cmd.extend(["-m", chosen_model])

        # 使用 '-' 从标准输入读取提示词
        cmd.append("-")

        # 准备环境变量（保持代理与系统环境）
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            logger.info(f"[CodexAdapter] 启动 codex exec 调用 (Model: {chosen_model or 'Default'})...")
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=tempfile.gettempdir(),
            )

            stdout_data, stderr_data = proc.communicate(input=full_prompt, timeout=self.timeout)

            # 优先从 -o 临时文件中读取纯净输出
            result_text = ""
            if os.path.exists(temp_out_path):
                with open(temp_out_path, "r", encoding="utf-8", errors="replace") as f:
                    result_text = f.read().strip()

            # 如果临时文件为空，尝试从 stdout 中提取备用
            if not result_text and stdout_data:
                result_text = stdout_data.strip()

            if not result_text:
                if proc.returncode != 0:
                    err_msg = stderr_data.strip() or stdout_data.strip() or f"退出代码 {proc.returncode}"
                    logger.error(f"[CodexAdapter] 执行失败: {err_msg}")
                    raise RuntimeError(f"Codex 执行失败: {err_msg}")
                else:
                    logger.warning("[CodexAdapter] Codex 未返回任何文本输出")

            return result_text

        except subprocess.TimeoutExpired:
            proc.kill()
            raise TimeoutError(f"Codex 调用超时（超过 {self.timeout} 秒）")
        except Exception as e:
            logger.error(f"[CodexAdapter] 调用异常: {e}", exc_info=True)
            raise
        finally:
            if os.path.exists(temp_out_path):
                try:
                    os.remove(temp_out_path)
                except Exception:
                    pass
