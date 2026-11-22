import json
from typing import Any, Dict, List, Literal, Optional
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from app.llm.structured import call_llm_structured


class LintIssue(BaseModel):
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    category: Literal["OVERDUE_HOOK", "TIMELINE_DRIFT", "POWER_CONFLICT", "OOC"]
    chapter_ref: int
    description: str = Field(..., description="具体矛盾点或超期说明")
    suggestion: str = Field(..., description="修复或回收建议")


class LintReport(BaseModel):
    checked_up_to_chapter: int
    issues: List[LintIssue] = Field(default_factory=list)


class NovelLinter:
    """
    全书离线体检工具：
    1. 零 Token 规则引擎：排查埋下超过 N 章仍未回收的僵尸伏笔
    2. 大模型长文本审计：审计最近数十篇摘要与全书绝对铁律，严查季节漂移、战力崩塌与人物 OOC
    """
    def __init__(self, overdue_threshold: int = 100):
        self.overdue_threshold = overdue_threshold

    def scan_overdue_foreshadowing(
        self,
        current_chapter: int,
        foreshadowing_list: List[Dict[str, Any]],
    ) -> List[LintIssue]:
        """纯规则扫描（0 Token 消耗）"""
        issues: List[LintIssue] = []
        for hook in foreshadowing_list:
            if hook.get("status") == "unresolved":
                planted_ch = hook.get("planted_chapter", 0)
                gap = current_chapter - planted_ch
                if gap >= self.overdue_threshold:
                    issues.append(LintIssue(
                        severity="MEDIUM",
                        category="OVERDUE_HOOK",
                        chapter_ref=planted_ch,
                        description=f"伏笔【{hook.get('summary')}】已埋下 {gap} 章仍未回收。",
                        suggestion="建议在下一卷细纲中安排回收，或在状态表中手动标为废弃。",
                    ))
        return issues

    async def audit_recent_summaries(
        self,
        current_chapter: int,
        recent_summaries: List[Dict[str, Any]],
        world_iron_rules: List[str],
        client: AsyncOpenAI,
        model: str = "deepseek-chat",
    ) -> List[LintIssue]:
        """大模型长文本审计"""
        prompt = (
            f"【全书绝对铁律】\n{json.dumps(world_iron_rules, ensure_ascii=False)}\n\n"
            f"【最近章节摘要】\n{json.dumps(recent_summaries, ensure_ascii=False)}\n\n"
            f"请作为严格的主编，逐条排查上述摘要中是否存在：\n"
            f"1. 时间线与季节/年龄漂移（如前文过冬后文突兀变盛夏，或主角年龄没随时间增长）\n"
            f"2. 违反全书铁律或战力体系前后矛盾\n"
            f"3. 关键角色性格前后严重割裂（OOC）\n"
            f"如果没有明显硬伤，issues 返回空列表即可，严禁吹毛求疵。"
        )

        report: LintReport = await call_llm_structured(
            client=client,
            model=model,
            system_prompt="你是严谨的长篇小说设定审计主编。",
            user_prompt=prompt,
            response_model=LintReport,
        )
        return report.issues

    async def run_full_check(
        self,
        current_chapter: int,
        foreshadowing_list: List[Dict[str, Any]],
        recent_summaries: List[Dict[str, Any]],
        world_iron_rules: List[str],
        client: Optional[AsyncOpenAI] = None,
        model: str = "deepseek-chat",
    ) -> LintReport:
        rule_issues = self.scan_overdue_foreshadowing(current_chapter, foreshadowing_list)
        llm_issues = []
        if client and recent_summaries:
            llm_issues = await self.audit_recent_summaries(
                current_chapter, recent_summaries, world_iron_rules, client, model
            )
        return LintReport(
            checked_up_to_chapter=current_chapter,
            issues=rule_issues + llm_issues,
        )
