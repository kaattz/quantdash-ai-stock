"""集中定义所有 Pydantic 数据模型，各模块共享。

使用 StrictModel 基类（extra="forbid", str_strip_whitespace=True），
与上游保持一致，提升输入校验严格性。
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """严格校验基类：禁止未知字段，自动去除字符串首尾空白。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# 股票数据
# ---------------------------------------------------------------------------


class StockPayload(StrictModel):
    symbol: str
    name: str
    price: float
    pctChange: float
    volume: str
    turnover: str
    industry: str
    concepts: List[str]
    pe: float = 0.0
    pb: float = 0.0
    marketCap: float = 0.0


# ---------------------------------------------------------------------------
# 认证
# ---------------------------------------------------------------------------


class AuthRequest(StrictModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=6)


class AuthResponse(StrictModel):
    token: str
    username: str


class MeResponse(StrictModel):
    username: str


# ---------------------------------------------------------------------------
# 自选股 & 监控
# ---------------------------------------------------------------------------


class MonitorCondition(StrictModel):
    id: Optional[str] = None
    type: Literal["volume_ratio", "price_touch_ma"]
    label: Optional[str] = None
    enabled: bool = True
    ratio: Optional[float] = None
    lookbackDays: Optional[int] = None
    minVolume: Optional[float] = None
    maWindow: Optional[int] = None
    tolerancePct: Optional[float] = None


class MonitorSignal(StrictModel):
    conditionId: Optional[str] = None
    conditionType: str
    triggered: bool
    checkedAt: str
    message: str
    metrics: Dict[str, Any] = Field(default_factory=dict)


class WatchlistEntry(StrictModel):
    symbol: str
    name: str
    price: float
    pctChange: float
    volume: str
    turnover: str
    industry: str
    concepts: List[str]
    pe: Optional[float] = None
    pb: Optional[float] = None
    marketCap: Optional[float] = None
    screenerSource: Optional[Dict[str, Any]] = None
    monitorConditions: List[MonitorCondition] = Field(default_factory=list)
    monitorSignals: List[MonitorSignal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 密码修改
# ---------------------------------------------------------------------------


class ChangePasswordRequest(StrictModel):
    oldPassword: str = Field(min_length=6)
    newPassword: str = Field(min_length=6)


# ---------------------------------------------------------------------------
# 同步
# ---------------------------------------------------------------------------


class SyncTriggerResponse(StrictModel):
    status: str
    trigger: str
    mode: str
    startedAt: str
    pid: Optional[int] = None


# ---------------------------------------------------------------------------
# 飞书集成
# ---------------------------------------------------------------------------


class FeishuBotConfigPayload(StrictModel):
    appId: str = ""
    appSecret: str = ""
    verificationToken: str = ""
    aiBaseUrl: str = ""
    aiApiKey: str = ""
    aiModel: str = ""


class FeishuBotConfigTestResult(StrictModel):
    ok: bool
    kind: Literal["success", "warning", "error"]
    statusLabel: str
    detail: str
    checkedAt: str


# ---------------------------------------------------------------------------
# 模型代理
# ---------------------------------------------------------------------------


class ModelInvokePayload(StrictModel):
    providerKey: str = ""
    protocol: Literal["openai", "anthropic", "gemini", "custom"] = "openai"
    baseUrl: str
    apiKey: str = ""
    model: str
    systemPrompt: str = ""
    userPrompt: str
    temperature: float = 0.2
    maxTokens: Optional[int] = None


class ModelInvokeResponse(StrictModel):
    content: str


# ---------------------------------------------------------------------------
# Skill Library（游资 skills）
# ---------------------------------------------------------------------------


class SkillLibraryEntry(StrictModel):
    id: str
    name: str
    description: str = ""
    instructions: str
    scopes: List[
        Literal[
            "reportSummary",
            "dailyReview",
            "ultraShortAnalysis",
            "premarketPlan",
            "stockObservation",
            "planValidation",
        ]
    ] = Field(default_factory=list)
    fileName: str
    sourceTitle: str
    updatedAt: str
    readOnly: bool = True


class SkillLibraryResponse(StrictModel):
    entries: List[SkillLibraryEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 前向引用重建（WatchlistEntry 引用了 MonitorCondition / MonitorSignal）
# ---------------------------------------------------------------------------

WatchlistEntry.model_rebuild()
