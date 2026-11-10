from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from chat import (
    ROOT,
    json_text,
    run_model_tool_loop,
    safe_slug,
    trim_history,
    write_transcript,
)
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


PROVIDER_KEY_ENV = {
    "OpenRouter": "OPENROUTER_API_KEY",
    "OpenAI": "OPENAI_API_KEY",
    "Anthropic": "ANTHROPIC_API_KEY",
    "Gemini": "GEMINI_API_KEY",
}
PROVIDER_NAMES = {
    "OpenRouter": "openrouter",
    "OpenAI": "openai",
    "Anthropic": "anthropic",
    "Gemini": "gemini",
    "Ollama (local)": "ollama",
}

load_lab_env(ROOT)
st.set_page_config(page_title="Research Agent | Lab Assistant", page_icon="🔎", layout="wide")


def init_state() -> None:
    defaults: dict[str, Any] = {
        "messages": [],
        "turns": [],
        "connected_config": None,
        "transcript_id": None,
        "transcript": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def provider_model(provider_name: str, custom_model: str) -> str | None:
    model = custom_model.strip()
    return model or None


def make_transcript(provider_name: str, model: str | None, version: str) -> dict[str, Any]:
    prompt_path = ROOT / "artifacts" / "system_prompt.md"
    tools_path = ROOT / "artifacts" / "tools.yaml"
    artifact_version = build_artifact_version(version, prompt_path, tools_path)
    transcript_id = "_".join(
        [
            safe_slug(version),
            safe_slug(provider_name),
            datetime.now().strftime("%Y%m%dT%H%M%S%f"),
        ]
    )
    st.session_state.transcript_id = transcript_id
    return {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": provider_name,
        "model": model,
        "system_prompt": str(prompt_path),
        "tools": str(tools_path),
        "history_window": st.session_state.history_window,
        "max_tool_rounds": st.session_state.max_tool_rounds,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "turns": [],
    }


init_state()
st.title("🔎 Research Agent")
st.caption(
    "Kết nối Agent để nghiên cứu yêu cầu bài lab, tìm nguồn và tạo checklist có thể đối chiếu."
)

with st.sidebar:
    st.header("Kết nối Agent")
    provider_label = st.selectbox("Provider", list(PROVIDER_NAMES))
    provider_id = PROVIDER_NAMES[provider_label]
    key_env = PROVIDER_KEY_ENV.get(provider_label)
    configured_key = bool(key_env and os.getenv(key_env))
    if key_env:
        api_key = st.text_input(
            f"{key_env} (để trống nếu đã cấu hình trong .env)",
            type="password",
            help="Khóa chỉ được dùng trong phiên chạy này, không ghi vào transcript.",
        )
    else:
        api_key = ""
        st.info("Ollama chạy trên máy cục bộ, không cần API key.")

    custom_model = st.text_input("Model", placeholder="Để trống dùng model mặc định")
    version = st.text_input("Phiên bản prompt", value="v0")
    st.session_state.history_window = st.slider("Số lượt chat giữ trong ngữ cảnh", 1, 10, 5)
    st.session_state.max_tool_rounds = st.slider("Số vòng gọi tool tối đa", 1, 8, 4)

    if st.button("Kết nối và kiểm tra", type="primary", use_container_width=True):
        if key_env and api_key.strip():
            os.environ[key_env] = api_key.strip()
        try:
            provider = make_provider(provider_id)
            model = provider_model(provider_id, custom_model)
            response = provider.complete(
                [{"role": "user", "content": "Reply with exactly: CONNECTED"}],
                [],
                model=model,
                temperature=0.0,
            )
            st.session_state.connected_config = {
                "provider": provider_id,
                "model": model or getattr(provider, "default_model", None),
            }
            st.success("Đã kết nối Agent.")
            if response.text:
                st.caption(f"Phản hồi kiểm tra: {response.text}")
        except Exception as exc:
            st.session_state.connected_config = None
            st.error(f"Kết nối thất bại: {type(exc).__name__}: {exc}")

    current_model = provider_model(provider_id, custom_model)
    if current_model is None:
        current_model = getattr(make_provider(provider_id), "default_model", None)
    is_connected = st.session_state.connected_config is not None
    config_matches = (
        is_connected
        and st.session_state.connected_config["provider"] == provider_id
        and st.session_state.connected_config["model"] == current_model
    )
    if config_matches:
        st.success("Agent đang sẵn sàng.")
    else:
        st.warning("Hãy kết nối Agent trước khi gửi tin nhắn.")

    if key_env and not configured_key and not api_key.strip():
        st.caption(f"Cần nhập {key_env} hoặc cấu hình trong file `.env`.")

    st.divider()
    st.subheader("Link demo")
    st.caption("Link local dùng khi app đang chạy trên máy này:")
    st.code("http://localhost:8501", language="text")
    st.caption(
        "Muốn có link public, deploy app lên Streamlit Community Cloud từ repo GitHub "
        "và thêm API key vào mục Secrets."
    )
    if st.button("Xóa hội thoại", use_container_width=True):
        st.session_state.messages = []
        st.session_state.turns = []
        st.session_state.transcript = None
        st.session_state.transcript_id = None
        st.rerun()

st.markdown(
    """
    **Gợi ý:** gửi link repository/tài liệu và yêu cầu Agent liệt kê đầu ra bắt buộc,
    tiêu chí chấm, deadline; yêu cầu gắn nguồn cho từng mục và tự kiểm tra lại checklist.
    """
)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("tool_events"):
            with st.expander("Chi tiết các tool đã dùng"):
                st.code(json_text(message["tool_events"]), language="json")

user_text = st.chat_input("Nhập câu hỏi hoặc dán link tài liệu/repository...")
if user_text:
    if not config_matches:
        st.warning("Vui lòng kết nối Agent trước khi chat.")
        st.stop()

    with st.chat_message("user"):
        st.markdown(user_text)
    st.session_state.messages.append({"role": "user", "content": user_text})

    with st.chat_message("assistant"):
        with st.spinner("Agent đang nghiên cứu..."):
            try:
                provider = make_provider(provider_id)
                system_prompt_path = ROOT / "artifacts" / "system_prompt.md"
                tools_path = ROOT / "artifacts" / "tools.yaml"
                system_prompt = system_prompt_path.read_text(encoding="utf-8")
                declarations = load_tool_declarations(tools_path)
                # The UI does not expose Telegram sending; all other declared tools remain available.
                declarations = [item for item in declarations if item.get("name") != "send"]
                tools = to_openai_tools(declarations)
                model = current_model or getattr(provider, "default_model", None)
                messages = [
                    {"role": "system", "content": system_prompt},
                    *trim_history(st.session_state.messages[:-1], st.session_state.history_window),
                    {"role": "user", "content": user_text},
                ]
                result = run_model_tool_loop(
                    provider=provider,
                    messages=messages,
                    tools=tools,
                    model=model,
                    max_tool_rounds=st.session_state.max_tool_rounds,
                )
                assistant_text = result["assistant_text"] or "Agent chưa trả về nội dung."
                st.markdown(assistant_text)
                tool_events = result["tool_events"]
                if tool_events:
                    with st.expander("Chi tiết các tool đã dùng"):
                        st.code(json_text(tool_events), language="json")

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_text,
                        "tool_events": tool_events,
                    }
                )
                if st.session_state.transcript is None:
                    st.session_state.transcript = make_transcript(provider_id, model, version)
                st.session_state.transcript["turns"].append(
                    {
                        "turn_index": len(st.session_state.transcript["turns"]) + 1,
                        "started_at": datetime.now().isoformat(timespec="seconds"),
                        "ended_at": datetime.now().isoformat(timespec="seconds"),
                        "user": user_text,
                        **result,
                    }
                )
                transcript_path = (
                    ROOT / "transcripts" / f"{st.session_state.transcript_id}.transcript.json"
                )
                write_transcript(transcript_path, st.session_state.transcript)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                st.error(f"Agent gặp lỗi: {error}")
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"Không thể xử lý yêu cầu: {error}"}
                )
