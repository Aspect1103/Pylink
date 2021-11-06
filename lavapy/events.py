"""
MIT License

Copyright (c) 2021-present Aspect1103

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .tracks import Track
    from .player import Player

__all__ = ("LavapyEvent",
           "TrackStartEvent",
           "TrackEndEvent",
           "TrackExceptionEvent",
           "TrackStuckEvent",
           "WebsocketClosedEvent")


class LavapyEvent:
    """
    Base Lavapy event. Every event inherits from this.

    If you want to listen to these events, use a :meth:`discord.ext.commands.Bot.listen()`.

    Parameters
    ----------
    player: Player
        A Lavapy Player object.

    Attributes
    ----------
    event: str
        The event name which has been dispatched.
    """
    def __init__(self, event: str, player: Player) -> None:
        self.event: str = event
        self._payload: Dict[str, Any] = {"player": player}

    def __repr__(self) -> str:
        return f"<Lavapy LavapyEvent (Payload={self.payload})>"

    @property
    def payload(self) -> Dict[str, Any]:
        """Returns a dict containing the payload sent to :meth:`discord.ext.commands.Bot.dispatch()`. This must be sent to `**kwargs`."""
        return self._payload


class TrackStartEvent(LavapyEvent):
    """
    Fired when a track starts playing. This can be listened to with:

    .. code-block:: python

        @bot.listen()
        async def on_lavapy_track_start(player, track):
            pass

    Parameters
    ----------
    player: Player
        A Lavapy Player object.
    track: Track
        A Lavapy Track object.
    """
    def __init__(self, player: Player, track: Track) -> None:
        super().__init__("track_start", player)
        self._payload["track"]: Dict[str, Any] = track

    def __repr__(self) -> str:
        return f"<Lavapy TrackStartEvent (Payload={self.payload})>"


class TrackEndEvent(LavapyEvent):
    """
    Fired when a track stops playing. This can be listened to with:

    .. code-block:: python

        @bot.listen()
        async def on_lavapy_track_end(player, track, reason):
            pass

    Parameters
    ----------
    player: Player
        A Lavapy Player object.
    track: Track
        A Lavapy Track object.
    data: Dict[str, Any]
        The raw event data.
    """
    def __init__(self, player: Player, track: Track, data: Dict[str, Any]) -> None:
        super().__init__("track_end", player)
        self._payload["track"]: Dict[str, Any] = track
        self._payload["reason"]: Dict[str, Any] = data["reason"]

    def __repr__(self) -> str:
        return f"<Lavapy TrackStopEvent (Payload={self.payload})>"


class TrackExceptionEvent(LavapyEvent):
    """
    Fired when a track error has occurred in Lavalink. This can be listened to with:

    .. code-block:: python

        @bot.listen()
        async def on_lavapy_track_exception(player, track, exception):
            pass

    Parameters
    ----------
    player: Player
        A Lavapy Player object.
    track: Track
        A Lavapy Track object.
    data: Dict[str, Any]
        The raw event data.
    """
    def __init__(self, player: Player, track: Track, data: Dict[str, Any]) -> None:
        super().__init__("track_exception", player)
        self._payload["track"]: Dict[str, Any] = track
        if data.get("error"):
            # User is running Lavalink <= 3.3
            self._payload["exception"]: Dict[str, Any] = data["error"]
        else:
            # User is running Lavalink >= 3.4
            self._payload["exception"]: Dict[str, Any] = data["exception"]

    def __repr__(self) -> str:
        return f"<Lavapy TrackExceptionEvent (Payload={self.payload})>"


class TrackStuckEvent(LavapyEvent):
    """
    Fired when a track is stuck and cannot be played. This can be listened to with:

    .. code-block:: python

        @bot.listen()
        async def on_lavapy_track_stuck(player, track, threshold):
            pass

    Parameters
    ----------
    player: Player
        A Lavapy Player object.
    track: Track
        A Lavapy Track object.
    data: Dict[str, Any]
        The raw event data.
    """
    def __init__(self, player: Player, track: Track, data: Dict[str, Any]) -> None:
        super().__init__("track_stuck", player)
        self._payload["track"]: Dict[str, Any] = track
        self._payload["threshold"]: Dict[str, Any] = data["thresholdMs"]

    def __repr__(self) -> str:
        return f"<Lavapy TrackStuckEvent (Payload={self.payload})>"


class WebsocketClosedEvent(LavapyEvent):
    """
    Fired when a websocket connection to a node is closed. This can be listened to with:

    .. code-block:: python

        @bot.listen()
        async def on_lavapy_websocket_closed(player, reason, code, byRemote):
            pass

    Parameters
    ----------
    player: Player
        A Lavapy Player object.
    data: Dict[str, Any]
        The raw event data.
    """
    def __init__(self, player: Player, data: Dict[str, Any]) -> None:
        super().__init__("websocket_closed", player)
        self._payload["reason"]: Dict[str, Any] = data["reason"]
        self._payload["code"]: Dict[str, Any] = data["code"]
        self._payload["byRemote"]: Dict[str, Any] = data["byRemote"]

    def __repr__(self) -> str:
        return f"<Lavapy WebsocketClosedEvent (Payload={self.payload})>"
