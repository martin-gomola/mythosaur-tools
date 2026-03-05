from __future__ import annotations

import base64
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import ToolDef, err, now_ms, ok, parse_int, resolve_under_workspace


@dataclass
class BrowserSession:
    session_id: str
    playwright: Any
    browser: Any
    context: Any
    page: Any


class BrowserManager:
    def __init__(self) -> None:
        self.sessions: dict[str, BrowserSession] = {}

    def enabled(self) -> bool:
        return (os.getenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED") or "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _create(self, session_id: str | None = None) -> BrowserSession:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError("playwright is not installed") from exc

        sid = (session_id or "").strip() or f"browser-{uuid.uuid4().hex[:12]}"
        pw = sync_playwright().start()
        headless = (os.getenv("MYTHOSAUR_TOOLS_BROWSER_HEADLESS") or "true").strip().lower() != "false"
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        sess = BrowserSession(session_id=sid, playwright=pw, browser=browser, context=context, page=page)
        self.sessions[sid] = sess
        return sess

    def get(self, session_id: str | None = None, create: bool = True) -> BrowserSession:
        sid = (session_id or "").strip()
        if sid and sid in self.sessions:
            return self.sessions[sid]
        if not create:
            raise KeyError(f"unknown browser session: {sid}")
        return self._create(session_id=sid or None)

    def close(self, session_id: str) -> None:
        sess = self.sessions.pop(session_id, None)
        if not sess:
            return
        try:
            sess.context.close()
            sess.browser.close()
            sess.playwright.stop()
        except Exception:
            pass


BROWSER = BrowserManager()


def _not_enabled(tool: str, started: int) -> dict:
    return err(tool, "disabled", "browser tools disabled (set MYTHOSAUR_TOOLS_BROWSER_ENABLED=true)", "browser", started)


def _navigate(args: dict) -> dict:
    started = now_ms()
    if not BROWSER.enabled():
        return _not_enabled("browser_navigate", started)
    url = (args.get("url") or "").strip()
    if not url:
        return err("browser_navigate", "missing_url", "url is required", "browser", started)
    wait_until = (args.get("wait_until") or "domcontentloaded").strip()
    try:
        sess = BROWSER.get(args.get("session_id"), create=True)
        sess.page.goto(url, wait_until=wait_until, timeout=parse_int(args.get("timeout_ms"), 30000, 1000, 120000))
        title = sess.page.title()
        return ok("browser_navigate", {"session_id": sess.session_id, "url": sess.page.url, "title": title}, "browser", started)
    except Exception as exc:
        return err("browser_navigate", "navigate_failed", str(exc), "browser", started)


def _snapshot(args: dict) -> dict:
    started = now_ms()
    if not BROWSER.enabled():
        return _not_enabled("browser_snapshot", started)
    try:
        sess = BROWSER.get(args.get("session_id"), create=False)
        text = sess.page.evaluate("() => document.body ? document.body.innerText : ''")
        text = (text or "").strip()
        max_chars = parse_int(args.get("max_chars"), 8000, 100, 200000)
        if len(text) > max_chars:
            text = f"{text[:max_chars]}\n\n[truncated]"
        return ok("browser_snapshot", {"session_id": sess.session_id, "url": sess.page.url, "text": text}, "browser", started)
    except Exception as exc:
        return err("browser_snapshot", "snapshot_failed", str(exc), "browser", started)


def _click(args: dict) -> dict:
    return _with_selector_action("browser_click", args, lambda page, sel: page.click(sel))


def _type(args: dict) -> dict:
    started = now_ms()
    if not BROWSER.enabled():
        return _not_enabled("browser_type", started)
    selector = (args.get("selector") or "").strip()
    text = str(args.get("text") or "")
    if not selector:
        return err("browser_type", "missing_selector", "selector is required", "browser", started)
    try:
        sess = BROWSER.get(args.get("session_id"), create=False)
        if bool(args.get("clear", True)):
            sess.page.fill(selector, "")
        sess.page.fill(selector, text)
        return ok("browser_type", {"session_id": sess.session_id, "selector": selector}, "browser", started)
    except Exception as exc:
        return err("browser_type", "type_failed", str(exc), "browser", started)


def _select(args: dict) -> dict:
    started = now_ms()
    if not BROWSER.enabled():
        return _not_enabled("browser_select", started)
    selector = (args.get("selector") or "").strip()
    value = str(args.get("value") or "")
    if not selector:
        return err("browser_select", "missing_selector", "selector is required", "browser", started)
    try:
        sess = BROWSER.get(args.get("session_id"), create=False)
        sess.page.select_option(selector, value=value)
        return ok("browser_select", {"session_id": sess.session_id, "selector": selector, "value": value}, "browser", started)
    except Exception as exc:
        return err("browser_select", "select_failed", str(exc), "browser", started)


def _hover(args: dict) -> dict:
    return _with_selector_action("browser_hover", args, lambda page, sel: page.hover(sel))


def _scroll(args: dict) -> dict:
    started = now_ms()
    if not BROWSER.enabled():
        return _not_enabled("browser_scroll", started)
    x = parse_int(args.get("x"), 0)
    y = parse_int(args.get("y"), 300)
    try:
        sess = BROWSER.get(args.get("session_id"), create=False)
        sess.page.mouse.wheel(x, y)
        return ok("browser_scroll", {"session_id": sess.session_id, "x": x, "y": y}, "browser", started)
    except Exception as exc:
        return err("browser_scroll", "scroll_failed", str(exc), "browser", started)


def _press_key(args: dict) -> dict:
    started = now_ms()
    if not BROWSER.enabled():
        return _not_enabled("browser_press_key", started)
    key = (args.get("key") or "").strip()
    if not key:
        return err("browser_press_key", "missing_key", "key is required", "browser", started)
    try:
        sess = BROWSER.get(args.get("session_id"), create=False)
        sess.page.keyboard.press(key)
        return ok("browser_press_key", {"session_id": sess.session_id, "key": key}, "browser", started)
    except Exception as exc:
        return err("browser_press_key", "press_failed", str(exc), "browser", started)


def _wait_for(args: dict) -> dict:
    started = now_ms()
    if not BROWSER.enabled():
        return _not_enabled("browser_wait_for", started)
    selector = (args.get("selector") or "").strip()
    timeout_ms = parse_int(args.get("timeout_ms"), 5000, 100, 120000)
    state = (args.get("state") or "visible").strip() or "visible"
    if not selector:
        return err("browser_wait_for", "missing_selector", "selector is required", "browser", started)
    try:
        sess = BROWSER.get(args.get("session_id"), create=False)
        sess.page.wait_for_selector(selector, timeout=timeout_ms, state=state)
        return ok("browser_wait_for", {"session_id": sess.session_id, "selector": selector, "state": state}, "browser", started)
    except Exception as exc:
        return err("browser_wait_for", "wait_failed", str(exc), "browser", started)


def _screenshot(args: dict) -> dict:
    started = now_ms()
    if not BROWSER.enabled():
        return _not_enabled("browser_screenshot", started)
    path = (args.get("path") or "").strip()
    full_page = bool(args.get("full_page", True))
    try:
        sess = BROWSER.get(args.get("session_id"), create=False)
        if path:
            out_path = resolve_under_workspace(path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            sess.page.screenshot(path=str(out_path), full_page=full_page)
            return ok("browser_screenshot", {"session_id": sess.session_id, "path": str(out_path), "url": sess.page.url}, "browser", started)
        png = sess.page.screenshot(full_page=full_page)
        b64 = base64.b64encode(png).decode("ascii")
        return ok("browser_screenshot", {"session_id": sess.session_id, "url": sess.page.url, "image_base64": b64}, "browser", started)
    except Exception as exc:
        return err("browser_screenshot", "screenshot_failed", str(exc), "browser", started)


def _execute_script(args: dict) -> dict:
    started = now_ms()
    if not BROWSER.enabled():
        return _not_enabled("browser_execute_script", started)
    script = (args.get("script") or "").strip()
    arg = args.get("arg")
    if not script:
        return err("browser_execute_script", "missing_script", "script is required", "browser", started)
    try:
        sess = BROWSER.get(args.get("session_id"), create=False)
        result = sess.page.evaluate(script, arg)
        return ok("browser_execute_script", {"session_id": sess.session_id, "result": result}, "browser", started)
    except Exception as exc:
        return err("browser_execute_script", "script_failed", str(exc), "browser", started)


def _with_selector_action(tool_name: str, args: dict, fn) -> dict:
    started = now_ms()
    if not BROWSER.enabled():
        return _not_enabled(tool_name, started)
    selector = (args.get("selector") or "").strip()
    if not selector:
        return err(tool_name, "missing_selector", "selector is required", "browser", started)
    try:
        sess = BROWSER.get(args.get("session_id"), create=False)
        fn(sess.page, selector)
        return ok(tool_name, {"session_id": sess.session_id, "selector": selector}, "browser", started)
    except Exception as exc:
        return err(tool_name, "action_failed", str(exc), "browser", started)


def get_tools() -> list[ToolDef]:
    obj = {"type": "object", "additionalProperties": False, "properties": {}, "required": []}

    return [
        ToolDef("browser_navigate", "mythosaur.browser", "Navigate browser to URL.", {
            **obj,
            "properties": {
                "url": {"type": "string"},
                "session_id": {"type": "string"},
                "wait_until": {"type": "string", "default": "domcontentloaded"},
                "timeout_ms": {"type": "integer", "minimum": 100, "maximum": 120000},
            },
            "required": ["url"],
        }, _navigate, aliases=["osaurus.browser_navigate"]),
        ToolDef("browser_snapshot", "mythosaur.browser", "Get text snapshot from current page.", {
            **obj,
            "properties": {
                "session_id": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 100, "maximum": 200000, "default": 8000},
            },
            "required": ["session_id"],
        }, _snapshot, aliases=["osaurus.browser_snapshot"]),
        ToolDef("browser_click", "mythosaur.browser", "Click CSS selector.", {
            **obj,
            "properties": {"session_id": {"type": "string"}, "selector": {"type": "string"}},
            "required": ["session_id", "selector"],
        }, _click, aliases=["osaurus.browser_click"]),
        ToolDef("browser_type", "mythosaur.browser", "Type into field selector.", {
            **obj,
            "properties": {"session_id": {"type": "string"}, "selector": {"type": "string"}, "text": {"type": "string"}, "clear": {"type": "boolean", "default": True}},
            "required": ["session_id", "selector", "text"],
        }, _type, aliases=["osaurus.browser_type"]),
        ToolDef("browser_select", "mythosaur.browser", "Select option by value.", {
            **obj,
            "properties": {"session_id": {"type": "string"}, "selector": {"type": "string"}, "value": {"type": "string"}},
            "required": ["session_id", "selector", "value"],
        }, _select, aliases=["osaurus.browser_select"]),
        ToolDef("browser_hover", "mythosaur.browser", "Hover CSS selector.", {
            **obj,
            "properties": {"session_id": {"type": "string"}, "selector": {"type": "string"}},
            "required": ["session_id", "selector"],
        }, _hover, aliases=["osaurus.browser_hover"]),
        ToolDef("browser_scroll", "mythosaur.browser", "Scroll page by wheel offsets.", {
            **obj,
            "properties": {"session_id": {"type": "string"}, "x": {"type": "integer", "default": 0}, "y": {"type": "integer", "default": 300}},
            "required": ["session_id"],
        }, _scroll, aliases=["osaurus.browser_scroll"]),
        ToolDef("browser_press_key", "mythosaur.browser", "Press keyboard key.", {
            **obj,
            "properties": {"session_id": {"type": "string"}, "key": {"type": "string"}},
            "required": ["session_id", "key"],
        }, _press_key, aliases=["osaurus.browser_press_key"]),
        ToolDef("browser_wait_for", "mythosaur.browser", "Wait for selector state.", {
            **obj,
            "properties": {"session_id": {"type": "string"}, "selector": {"type": "string"}, "timeout_ms": {"type": "integer", "minimum": 100, "maximum": 120000, "default": 5000}, "state": {"type": "string", "default": "visible"}},
            "required": ["session_id", "selector"],
        }, _wait_for, aliases=["osaurus.browser_wait_for"]),
        ToolDef("browser_screenshot", "mythosaur.browser", "Take screenshot of current page.", {
            **obj,
            "properties": {"session_id": {"type": "string"}, "path": {"type": "string"}, "full_page": {"type": "boolean", "default": True}},
            "required": ["session_id"],
        }, _screenshot, aliases=["osaurus.browser_screenshot"]),
        ToolDef("browser_execute_script", "mythosaur.browser", "Execute page script.", {
            **obj,
            "properties": {"session_id": {"type": "string"}, "script": {"type": "string"}, "arg": {}},
            "required": ["session_id", "script"],
        }, _execute_script, aliases=["osaurus.browser_execute_script"]),
    ]
