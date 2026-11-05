"""身分提供者介面：Controller 只認這兩個方法，不知道背後是 Authlib 還是模擬頁面。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from flask import Response

from ...schemas.account import GoogleIdentity


class IdentityProvider(ABC):
    @abstractmethod
    def begin(self, callback_url: str) -> Response:
        """開始登入：回傳導向身分提供者（或模擬頁面）的 redirect 回應。"""

    @abstractmethod
    def complete(self) -> GoogleIdentity:
        """處理登入完成後的 callback 請求，回傳標準化的身分（讀取目前的 Flask request）。"""
