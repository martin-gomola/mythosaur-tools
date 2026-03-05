from __future__ import annotations

import shutil

from .common import ToolDef, err, is_readonly, now_ms, ok, parse_int, resolve_under_workspace


def _read_file(arguments: dict) -> dict:
    started = now_ms()
    path = (arguments.get("path") or "").strip()
    max_bytes = parse_int(arguments.get("max_bytes"), default=200_000, minimum=1_024, maximum=10_000_000)
    if not path:
        return err("read_file", "missing_path", "path is required", "filesystem", started)
    try:
        target = resolve_under_workspace(path)
        if not target.exists() or not target.is_file():
            return err("read_file", "not_file", f"file not found: {target}", "filesystem", started)
        raw = target.read_bytes()
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
        text = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        return err("read_file", "read_failed", str(exc), "filesystem", started)
    return ok("read_file", {"path": str(target), "content": text}, "filesystem", started)


def _write_file(arguments: dict) -> dict:
    started = now_ms()
    if is_readonly():
        return err("write_file", "forbidden", "write_file is blocked in readonly profile", "filesystem", started)
    path = (arguments.get("path") or "").strip()
    content = str(arguments.get("content") or "")
    mode = (arguments.get("mode") or "overwrite").strip().lower()
    if not path:
        return err("write_file", "missing_path", "path is required", "filesystem", started)
    if mode not in {"overwrite", "append"}:
        return err("write_file", "invalid_mode", "mode must be overwrite|append", "filesystem", started)
    try:
        target = resolve_under_workspace(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a" if mode == "append" else "w", encoding="utf-8") as fh:
            fh.write(content)
    except Exception as exc:
        return err("write_file", "write_failed", str(exc), "filesystem", started)
    return ok("write_file", {"path": str(target), "bytes": len(content.encode("utf-8")), "mode": mode}, "filesystem", started)


def _list_directory(arguments: dict) -> dict:
    started = now_ms()
    path = (arguments.get("path") or ".").strip()
    try:
        target = resolve_under_workspace(path)
        if not target.exists() or not target.is_dir():
            return err("list_directory", "not_directory", f"directory not found: {target}", "filesystem", started)
        entries = []
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower())[:500]:
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.exists() and child.is_file() else 0,
                }
            )
    except Exception as exc:
        return err("list_directory", "list_failed", str(exc), "filesystem", started)
    return ok("list_directory", {"path": str(target), "entries": entries}, "filesystem", started)


def _create_directory(arguments: dict) -> dict:
    started = now_ms()
    if is_readonly():
        return err("create_directory", "forbidden", "create_directory is blocked in readonly profile", "filesystem", started)
    path = (arguments.get("path") or "").strip()
    if not path:
        return err("create_directory", "missing_path", "path is required", "filesystem", started)
    try:
        target = resolve_under_workspace(path)
        target.mkdir(parents=True, exist_ok=bool(arguments.get("exist_ok", True)))
    except Exception as exc:
        return err("create_directory", "mkdir_failed", str(exc), "filesystem", started)
    return ok("create_directory", {"path": str(target)}, "filesystem", started)


def _delete_file(arguments: dict) -> dict:
    started = now_ms()
    if is_readonly():
        return err("delete_file", "forbidden", "delete_file is blocked in readonly profile", "filesystem", started)
    path = (arguments.get("path") or "").strip()
    recursive = bool(arguments.get("recursive", False))
    if not path:
        return err("delete_file", "missing_path", "path is required", "filesystem", started)
    try:
        target = resolve_under_workspace(path)
        if target.is_dir():
            if not recursive:
                return err("delete_file", "is_directory", "set recursive=true for directories", "filesystem", started)
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
    except Exception as exc:
        return err("delete_file", "delete_failed", str(exc), "filesystem", started)
    return ok("delete_file", {"path": str(target)}, "filesystem", started)


def _move_file(arguments: dict) -> dict:
    started = now_ms()
    if is_readonly():
        return err("move_file", "forbidden", "move_file is blocked in readonly profile", "filesystem", started)
    src = (arguments.get("src") or "").strip()
    dst = (arguments.get("dst") or "").strip()
    overwrite = bool(arguments.get("overwrite", False))
    if not src or not dst:
        return err("move_file", "missing_path", "src and dst are required", "filesystem", started)
    try:
        src_path = resolve_under_workspace(src)
        dst_path = resolve_under_workspace(dst)
        if not src_path.exists():
            return err("move_file", "missing_src", f"source not found: {src_path}", "filesystem", started)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if dst_path.exists() and not overwrite:
            return err("move_file", "dst_exists", f"destination exists: {dst_path}", "filesystem", started)
        src_path.replace(dst_path)
    except Exception as exc:
        return err("move_file", "move_failed", str(exc), "filesystem", started)
    return ok("move_file", {"src": str(src_path), "dst": str(dst_path)}, "filesystem", started)


def _search_files(arguments: dict) -> dict:
    started = now_ms()
    query = (arguments.get("query") or "").strip().lower()
    path = (arguments.get("path") or ".").strip()
    max_results = parse_int(arguments.get("max_results"), default=50, minimum=1, maximum=500)
    if not query:
        return err("search_files", "missing_query", "query is required", "filesystem", started)
    try:
        root = resolve_under_workspace(path)
        if not root.exists() or not root.is_dir():
            return err("search_files", "not_directory", f"directory not found: {root}", "filesystem", started)
        results = []
        for item in root.rglob("*"):
            if query in item.name.lower():
                results.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "type": "dir" if item.is_dir() else "file",
                    }
                )
                if len(results) >= max_results:
                    break
    except Exception as exc:
        return err("search_files", "search_failed", str(exc), "filesystem", started)

    return ok("search_files", {"query": query, "path": str(root), "results": results}, "filesystem", started)


def _get_file_info(arguments: dict) -> dict:
    started = now_ms()
    path = (arguments.get("path") or "").strip()
    if not path:
        return err("get_file_info", "missing_path", "path is required", "filesystem", started)
    try:
        target = resolve_under_workspace(path)
        if not target.exists():
            return err("get_file_info", "missing", f"path not found: {target}", "filesystem", started)
        stat = target.stat()
        info = {
            "path": str(target),
            "name": target.name,
            "type": "dir" if target.is_dir() else "file",
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        }
    except Exception as exc:
        return err("get_file_info", "stat_failed", str(exc), "filesystem", started)
    return ok("get_file_info", info, "filesystem", started)


def get_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="read_file",
            plugin_id="mythosaur.filesystem",
            description="Read UTF-8 text file under workspace root.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "max_bytes": {"type": "integer", "minimum": 1024, "maximum": 10000000, "default": 200000},
                },
                "required": ["path"],
            },
            handler=_read_file,
            aliases=["osaurus.read_file"],
        ),
        ToolDef(
            name="write_file",
            plugin_id="mythosaur.filesystem",
            description="Write file under workspace root (blocked in readonly profile).",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
                },
                "required": ["path", "content"],
            },
            handler=_write_file,
            aliases=["osaurus.write_file"],
        ),
        ToolDef(
            name="list_directory",
            plugin_id="mythosaur.filesystem",
            description="List directory entries under workspace root.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {"path": {"type": "string", "default": "."}},
                "required": [],
            },
            handler=_list_directory,
            aliases=["osaurus.list_directory"],
        ),
        ToolDef(
            name="create_directory",
            plugin_id="mythosaur.filesystem",
            description="Create directory under workspace root (blocked in readonly profile).",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "exist_ok": {"type": "boolean", "default": True},
                },
                "required": ["path"],
            },
            handler=_create_directory,
            aliases=["osaurus.create_directory"],
        ),
        ToolDef(
            name="delete_file",
            plugin_id="mythosaur.filesystem",
            description="Delete file/dir under workspace root (blocked in readonly profile).",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean", "default": False},
                },
                "required": ["path"],
            },
            handler=_delete_file,
            aliases=["osaurus.delete_file"],
        ),
        ToolDef(
            name="move_file",
            plugin_id="mythosaur.filesystem",
            description="Move file under workspace root (blocked in readonly profile).",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "src": {"type": "string"},
                    "dst": {"type": "string"},
                    "overwrite": {"type": "boolean", "default": False},
                },
                "required": ["src", "dst"],
            },
            handler=_move_file,
            aliases=["osaurus.move_file"],
        ),
        ToolDef(
            name="search_files",
            plugin_id="mythosaur.filesystem",
            description="Search files/directories by name under workspace root.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
                },
                "required": ["query"],
            },
            handler=_search_files,
            aliases=["osaurus.search_files"],
        ),
        ToolDef(
            name="get_file_info",
            plugin_id="mythosaur.filesystem",
            description="Return metadata for a file/directory under workspace root.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
            handler=_get_file_info,
            aliases=["osaurus.get_file_info"],
        ),
    ]
