# novel_generator/zhuque_client.py
# -*- coding: utf-8 -*-
"""
腾讯云 朱雀 AIGC 文本检测客户端 (zhuque-text)
通过腾讯云 EdgeOne Makers (AI 网关) 接口对小说文本执行 AI 痕迹检测与病灶定位。
"""

import logging
import json
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ZhuqueClient")

DEFAULT_ZHUQUE_ENDPOINT = "https://ai-gateway.edgeone.link/v1/providers/zhuque-text/classify"


class ZhuqueAuditResult:
    """朱雀检测结果对象"""

    def __init__(
        self,
        success: bool,
        overall_confidence: float = 0.0,
        labels_ratio: Optional[Dict[str, float]] = None,
        segment_labels: Optional[List[Dict[str, Any]]] = None,
        toxic_segments: Optional[List[Dict[str, Any]]] = None,
        suspect_segments: Optional[List[Dict[str, Any]]] = None,
        message: str = "",
        is_mock: bool = False,
    ):
        self.success = bool(success)
        self.overall_confidence = round(overall_confidence, 4)
        # 0: 人类撰写, 1: AI 生成, 2: 疑似
        # 严格防御：若检测失败或异常，绝不能默认为 100% 人类撰写，必须默认标注为未通过 (AI: 1.0)
        if not self.success or is_mock:
            self.labels_ratio = labels_ratio or {"0": 0.0, "1": 1.0, "2": 0.0}
        else:
            self.labels_ratio = labels_ratio or {"0": 0.0, "1": 1.0, "2": 0.0}
        self.segment_labels = segment_labels or []
        # 被判定为 AI 生成 (label=1 且 conf 高) 的高危病灶段落
        self.toxic_segments = toxic_segments or []
        # 被判定为疑似/中性 (label=2) 的机械痕迹段落，供微创提升
        self.suspect_segments = suspect_segments or []
        self.message = message
        self.is_mock = is_mock

    @property
    def ai_rate(self) -> float:
        """AI 生成占比百分比 (0-100)"""
        ratio_1 = self.labels_ratio.get("1", self.labels_ratio.get(1, 0.0))
        return round(float(ratio_1) * 100, 1)

    @property
    def human_rate(self) -> float:
        """真人质感占比百分比 (0-100)"""
        ratio_0 = self.labels_ratio.get("0", self.labels_ratio.get(0, 0.0))
        return round(float(ratio_0) * 100, 1)

    @property
    def suspicious_rate(self) -> float:
        """疑似 AI 占比百分比 (0-100)"""
        ratio_2 = self.labels_ratio.get("2", self.labels_ratio.get(2, 0.0))
        return round(float(ratio_2) * 100, 1)

    @property
    def is_configured(self) -> bool:
        """是否有效完成客观自检（非空或非mock且检测成功）"""
        return not self.is_mock and self.success

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "overall_confidence": self.overall_confidence,
            "ai_rate": self.ai_rate,
            "human_rate": self.human_rate,
            "labels_ratio": self.labels_ratio,
            "segment_count": len(self.segment_labels),
            "toxic_count": len(self.toxic_segments),
            "toxic_segments": self.toxic_segments[:10],  # 最多返回前 10 个典型病灶供展示
            "suspect_count": len(self.suspect_segments),
            "suspect_segments": self.suspect_segments[:10],
            "message": self.message,
            "is_mock": self.is_mock,
        }


class ZhuqueAuditClient:
    """
    腾讯云朱雀检测客户端
    """

    def __init__(
        self,
        api_key: str = "",
        endpoint: str = DEFAULT_ZHUQUE_ENDPOINT,
        timeout: int = 25,
    ):
        self.api_key = (api_key or "").strip()
        self.endpoint = endpoint or DEFAULT_ZHUQUE_ENDPOINT
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """是否已配置有效 API Key"""
        return bool(self.api_key and len(self.api_key) > 6)

    def check_chunk(self, chunk_text: str) -> Dict[str, Any]:
        """单批次请求朱雀 API (<= 900 字符)，具备代理异常自动直连 fallback"""
        if not self.is_configured:
            return {"status": "error", "ok": False, "error": "未配置腾讯云 EdgeOne 朱雀 API Key"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": chunk_text,
            "is_merge": False,  # 保留段落独立判定
        }

        # 尝试请求，如果遭遇本地 SOCKS / 代理环境异常，自动 fallback 到直连 session
        for attempt in range(2):
            try:
                if attempt == 0:
                    resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout)
                else:
                    # 直连重试（忽略全局 SOCKS/HTTP 环境变量代理）
                    s = requests.Session()
                    s.trust_env = False
                    resp = s.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout)

                if resp.status_code != 200:
                    logger.error(f"[Zhuque] HTTP {resp.status_code}: {resp.text}")
                    return {"status": "error", "ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

                data = resp.json()
                # 兼容字段
                if "status" not in data and "ok" in data:
                    data["status"] = "success" if data.get("ok") else "error"
                if "ok" not in data:
                    data["ok"] = (data.get("status") == "success")
                if "confidence" not in data:
                    data["confidence"] = data.get("softmax_confidence", data.get("ratio_confidence", 0.0))
                return data
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"[Zhuque] 代理或首发连接异常 ({e})，正在自动切换直连重试...")
                    continue
                logger.error(f"[Zhuque] 请求异常: {e}")
                return {"status": "error", "ok": False, "error": str(e)}

        return {"status": "error", "ok": False, "error": "未知请求异常"}

    def audit_text(self, text: str) -> ZhuqueAuditResult:
        """
        对整篇章节文本执行完整检测。
        长文本按自然段切片，分批送检后汇总分析。
        """
        clean_text = (text or "").strip()
        if not clean_text:
            return ZhuqueAuditResult(success=True, message="文本为空，无需自检")

        if not self.is_configured:
            logger.info("[Zhuque] 未配置朱雀 Key，跳过客观检测")
            return ZhuqueAuditResult(
                success=True,
                message="未配置腾讯云朱雀 API Key，已跳过客观 AI 味评分",
                is_mock=True,
            )

        # 按自然段落切分为 batches（每批累计不超过 850 字符）
        paragraphs = [p.strip() for p in clean_text.split("\n") if p.strip()]
        batches: List[str] = []
        cur_batch = []
        cur_len = 0

        for p in paragraphs:
            if cur_len + len(p) > 850 and cur_batch:
                batches.append("\n\n".join(cur_batch))
                cur_batch = [p]
                cur_len = len(p)
            else:
                cur_batch.append(p)
                cur_len += len(p)

        if cur_batch:
            batches.append("\n\n".join(cur_batch))

        all_segments = []
        toxic_segments = []
        suspect_segments = []
        total_ai_weight = 0.0
        total_human_weight = 0.0
        total_unknown_weight = 0.0
        total_chars = 0

        success_count = 0

        for idx, batch in enumerate(batches):
            data = self.check_chunk(batch)
            is_success = data.get("status") == "success" or data.get("ok") is True or bool(data.get("segment_labels"))
            if not is_success:
                logger.warning(f"[Zhuque] 批次 {idx + 1}/{len(batches)} 检测失败: {data.get('error') or data.get('msg')}")
                continue

            success_count += 1
            b_len = max(len(batch), 1)
            total_chars += b_len

            segs = data.get("segment_labels") or []
            if not segs:
                # 兼容单段返回
                conf = float(data.get("confidence", data.get("softmax_confidence", 0.5)))
                segs = [{
                    "text": batch,
                    "label": 1 if conf >= 0.32 else (2 if conf >= 0.20 else 0),
                    "conf": conf,
                }]

            chunk_human_chars = 0
            chunk_ai_chars = 0
            chunk_suspect_chars = 0
            chunk_total_chars = 0

            for s in segs:
                s_text = s.get("text", "").strip()
                s_len = max(len(s_text), 1)
                s_conf = float(s.get("conf", 0.5))
                chunk_total_chars += s_len

                # 按照腾讯朱雀官方多模态 AI 检测平台 (matrix.tencent.com) 统一标准对齐：
                # 1. AI 特征 (Red): conf >= 0.30 或原始 label == 1
                # 2. 疑似 AI 特征 (Yellow): 0.20 <= conf < 0.30 或原始 label == 2
                # 3. 纯人工质感 (Green): conf < 0.20 且原始 label == 0
                if s_conf >= 0.30 or str(s.get("label")) == "1" or s.get("label") == 1:
                    chunk_ai_chars += s_len
                    s["calibrated_label"] = 1
                    toxic_segments.append({
                        "text": s_text,
                        "conf": round(s_conf, 3),
                        "type": "toxic",
                        "reason": f"AI特征置信度 {round(s_conf * 100, 1)}%",
                    })
                elif s_conf >= 0.20 or str(s.get("label")) == "2" or s.get("label") == 2:
                    chunk_suspect_chars += s_len
                    s["calibrated_label"] = 2
                    suspect_segments.append({
                        "text": s_text,
                        "conf": round(s_conf, 3),
                        "type": "suspect",
                        "reason": f"疑似AI套路化表达 (置信度 {round(s_conf * 100, 1)}%)",
                    })
                else:
                    chunk_human_chars += s_len
                    s["calibrated_label"] = 0

                all_segments.append(s)

            # 汇总全篇真实字数权重
            total_human_weight += chunk_human_chars
            total_ai_weight += chunk_ai_chars
            total_unknown_weight += chunk_suspect_chars
            total_chars += chunk_total_chars

        if success_count == 0:
            return ZhuqueAuditResult(
                success=False,
                message="所有批次请求朱雀自检失败，请检查网络或 Key 权限",
            )

        denom = max(total_chars, 1)
        calc_ai_ratio = round(total_ai_weight / denom, 4)
        calc_human_ratio = round(total_human_weight / denom, 4)
        calc_unk_ratio = max(0.0, round(1.0 - calc_ai_ratio - calc_human_ratio, 4))

        # 总体置信度取加权
        overall_conf = round(calc_ai_ratio if calc_ai_ratio >= calc_human_ratio else (1.0 - calc_human_ratio), 4)

        return ZhuqueAuditResult(
            success=True,
            overall_confidence=overall_conf,
            labels_ratio={
                "0": calc_human_ratio,
                "1": calc_ai_ratio,
                "2": calc_unk_ratio,
            },
            segment_labels=all_segments,
            toxic_segments=toxic_segments,
            suspect_segments=suspect_segments,
            message="朱雀自检分析完成",
        )
