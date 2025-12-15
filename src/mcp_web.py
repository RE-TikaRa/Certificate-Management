"""Local web controller for MCP tools (optional).

This is a convenience UI for calling the same read-only MCP tool functions from a browser.
It does not replace MCP clients; it helps you inspect data and validate MCP outputs quickly.
"""

from __future__ import annotations

import importlib
import json
import os
from typing import Any

from . import mcp_server


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _client_config_snippet() -> str:
    env = {
        "CERT_MCP_ALLOW_WRITE": "0",
        "CERT_MCP_MAX_BYTES": str(mcp_server.MAX_BYTES),
    }
    payload = {
        "mcpServers": {
            "certificate": {
                "command": "uv",
                "args": ["run", "certificate-mcp"],
                "env": env,
            }
        }
    }
    return _pretty(payload)


def main() -> None:
    try:
        gr = importlib.import_module("gradio")
    except Exception as exc:
        raise RuntimeError("gradio is not installed; run: uv sync --group mcp-web") from exc

    host = os.getenv("CERT_MCP_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("CERT_MCP_WEB_PORT", "7860"))
    inbrowser = os.getenv("CERT_MCP_WEB_INBROWSER", "1") == "1"

    def health_json() -> str:
        return _pretty(mcp_server.health())

    def list_awards_json(
        limit: int,
        offset: int,
        include_deleted: bool,
        level: str,
        rank: str,
        start_date: str,
        end_date: str,
        order_by: str,
    ) -> str:
        level_v = level.strip() or None
        rank_v = rank.strip() or None
        start_v = start_date.strip() or None
        end_v = end_date.strip() or None
        return _pretty(
            mcp_server.list_awards(
                limit=limit,
                offset=offset,
                include_deleted=include_deleted,
                level=level_v,
                rank=rank_v,
                start_date=start_v,
                end_date=end_v,
                order_by=order_by,
            )
        )

    def search_awards_json(
        query: str,
        limit: int,
        include_deleted: bool,
        level: str,
        rank: str,
        start_date: str,
        end_date: str,
    ) -> str:
        level_v = level.strip() or None
        rank_v = rank.strip() or None
        start_v = start_date.strip() or None
        end_v = end_date.strip() or None
        return _pretty(
            mcp_server.search_awards(
                query=query,
                limit=limit,
                include_deleted=include_deleted,
                level=level_v,
                rank=rank_v,
                start_date=start_v,
                end_date=end_v,
            )
        )

    def get_award_json(award_id: int, include_deleted: bool) -> str:
        return _pretty(mcp_server.get_award(award_id=award_id, include_deleted=include_deleted))

    def list_members_json(limit: int, offset: int, active_only: bool) -> str:
        return _pretty(mcp_server.list_members(limit=limit, offset=offset, active_only=active_only))

    def get_member_json(member_id: int) -> str:
        return _pretty(mcp_server.get_member(member_id=member_id))

    def read_attachment_json(relative_path: str, offset: int, length: int) -> str:
        return _pretty(mcp_server.read_attachment(relative_path=relative_path, offset=offset, length=length))

    with gr.Blocks(title="Certificate MCP Controller") as demo:
        gr.Markdown("# Certificate MCP Controller\n用于查看/调用 MCP 工具输出（本地）。")

        with gr.Tab("配置"):
            gr.Markdown("MCP 客户端配置片段（只读）：")
            cfg = gr.Code(value=_client_config_snippet(), language="json", label="mcp config")
            gr.Button("刷新").click(lambda: _client_config_snippet(), outputs=cfg)

        with gr.Tab("健康检查"):
            out = gr.Code(value=health_json(), language="json", label="health()")
            gr.Button("刷新").click(health_json, outputs=out)

        with gr.Tab("荣誉列表"):
            with gr.Row():
                limit = gr.Number(value=50, precision=0, label="limit")
                offset = gr.Number(value=0, precision=0, label="offset")
                include_deleted = gr.Checkbox(value=False, label="include_deleted")
            with gr.Row():
                level = gr.Text(label="level (可选)", placeholder="国家级/省级/校级…")
                rank = gr.Text(label="rank (可选)", placeholder="一等奖/二等奖/…")
            with gr.Row():
                start_date = gr.Text(label="start_date (ISO, 可选)", placeholder="2025-01-01")
                end_date = gr.Text(label="end_date (ISO, 可选)", placeholder="2025-12-31")
            order_by = gr.Dropdown(
                choices=["award_date_desc", "award_date_asc", "competition_name_asc", "competition_name_desc"],
                value="award_date_desc",
                label="order_by",
            )
            btn = gr.Button("执行")
            result = gr.Code(language="json", label="result")
            btn.click(
                list_awards_json,
                inputs=[limit, offset, include_deleted, level, rank, start_date, end_date, order_by],
                outputs=result,
            )

        with gr.Tab("荣誉搜索"):
            query = gr.Text(label="query", placeholder="比赛名/证书号/成员…")
            with gr.Row():
                limit2 = gr.Number(value=50, precision=0, label="limit")
                include_deleted2 = gr.Checkbox(value=False, label="include_deleted")
            with gr.Row():
                level2 = gr.Text(label="level (可选)")
                rank2 = gr.Text(label="rank (可选)")
            with gr.Row():
                start2 = gr.Text(label="start_date (ISO, 可选)")
                end2 = gr.Text(label="end_date (ISO, 可选)")
            btn2 = gr.Button("搜索")
            result2 = gr.Code(language="json", label="result")
            btn2.click(
                search_awards_json,
                inputs=[query, limit2, include_deleted2, level2, rank2, start2, end2],
                outputs=result2,
            )

        with gr.Tab("单条荣誉"):
            award_id = gr.Number(value=1, precision=0, label="award_id")
            include_deleted3 = gr.Checkbox(value=False, label="include_deleted")
            btn3 = gr.Button("获取")
            result3 = gr.Code(language="json", label="result")
            btn3.click(get_award_json, inputs=[award_id, include_deleted3], outputs=result3)

        with gr.Tab("成员"):
            with gr.Row():
                limit_m = gr.Number(value=50, precision=0, label="limit")
                offset_m = gr.Number(value=0, precision=0, label="offset")
                active_only = gr.Checkbox(value=True, label="active_only")
            btnm = gr.Button("列出")
            outm = gr.Code(language="json", label="list_members")
            btnm.click(list_members_json, inputs=[limit_m, offset_m, active_only], outputs=outm)
            member_id = gr.Number(value=1, precision=0, label="member_id")
            btnm2 = gr.Button("获取")
            outm2 = gr.Code(language="json", label="get_member")
            btnm2.click(get_member_json, inputs=[member_id], outputs=outm2)

        with gr.Tab("附件读取"):
            rel = gr.Text(label="relative_path", placeholder="例如：award_xxx/file.pdf")
            with gr.Row():
                off = gr.Number(value=0, precision=0, label="offset")
                length = gr.Number(value=mcp_server.MAX_BYTES, precision=0, label="length")
            btna = gr.Button("读取")
            outa = gr.Code(language="json", label="read_attachment")
            btna.click(read_attachment_json, inputs=[rel, off, length], outputs=outa)

    demo.launch(server_name=host, server_port=port, inbrowser=inbrowser)


if __name__ == "__main__":
    main()
