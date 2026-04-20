"""models.py 属性测试 — Property 11 & Property 12

使用 hypothesis 对 StrictModel 基类和 AuthRequest 进行属性验证。
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
from pydantic import ValidationError

from server.models import (
    AuthRequest,
    AuthResponse,
    ChangePasswordRequest,
    FeishuBotConfigPayload,
    FeishuBotConfigTestResult,
    MeResponse,
    ModelInvokePayload,
    ModelInvokeResponse,
    StrictModel,
    StockPayload,
    SyncTriggerResponse,
)


# ---------------------------------------------------------------------------
# Property 11: StrictModel 拒绝未知字段
# Feature: backend-modular-migration, Property 11: StrictModel 拒绝未知字段
# **Validates: Requirements 8.2**
# ---------------------------------------------------------------------------

# 选取具有简单必填字段的模型子类进行测试，构造合法基础数据后注入未知字段
_SIMPLE_MODELS_WITH_VALID_DATA: list[tuple[type, dict]] = [
    (AuthRequest, {"username": "testuser", "password": "secret123"}),
    (AuthResponse, {"token": "tok123", "username": "testuser"}),
    (MeResponse, {"username": "testuser"}),
    (ChangePasswordRequest, {"oldPassword": "secret123", "newPassword": "newsecret1"}),
    (SyncTriggerResponse, {"status": "ok", "trigger": "manual", "mode": "startup", "startedAt": "2024-01-01"}),
    (FeishuBotConfigPayload, {}),  # 所有字段有默认值
    (ModelInvokeResponse, {"content": "hello"}),
]

# 已知字段名集合，用于过滤生成的字段名
_ALL_KNOWN_FIELDS: set[str] = set()
for _cls, _ in _SIMPLE_MODELS_WITH_VALID_DATA:
    _ALL_KNOWN_FIELDS.update(_cls.model_fields.keys())


@settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
@given(
    model_index=st.integers(min_value=0, max_value=len(_SIMPLE_MODELS_WITH_VALID_DATA) - 1),
    extra_field=st.text(min_size=1, max_size=30).filter(lambda s: s.isidentifier()),
    extra_value=st.one_of(st.text(), st.integers(), st.booleans()),
)
def test_strict_model_rejects_unknown_fields(
    model_index: int,
    extra_field: str,
    extra_value,
):
    """对任意继承自 StrictModel 的模型类，传入未知字段应抛出 ValidationError。"""
    model_cls, valid_data = _SIMPLE_MODELS_WITH_VALID_DATA[model_index]

    # 确保生成的字段名不是该模型的已知字段
    assume(extra_field not in model_cls.model_fields)

    data_with_extra = {**valid_data, extra_field: extra_value}
    with pytest.raises(ValidationError):
        model_cls(**data_with_extra)


# ---------------------------------------------------------------------------
# Property 12: AuthRequest 校验短输入
# Feature: backend-modular-migration, Property 12: AuthRequest 校验短输入
# **Validates: Requirements 8.3**
# ---------------------------------------------------------------------------


@settings(max_examples=10)
@given(
    short_username=st.text(max_size=2),
    valid_password=st.text(min_size=6, max_size=30),
)
def test_auth_request_rejects_short_username(
    short_username: str,
    valid_password: str,
):
    """长度小于 3 的用户名应抛出 ValidationError。"""
    with pytest.raises(ValidationError):
        AuthRequest(username=short_username, password=valid_password)


@settings(max_examples=10)
@given(
    valid_username=st.text(min_size=3, max_size=30),
    short_password=st.text(max_size=5),
)
def test_auth_request_rejects_short_password(
    valid_username: str,
    short_password: str,
):
    """长度小于 6 的密码应抛出 ValidationError。"""
    with pytest.raises(ValidationError):
        AuthRequest(username=valid_username, password=short_password)
