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

import datetime
import logging
from datetime import datetime, timezone
from typing import Union, Optional, Any, Dict, Type

from discord import VoiceProtocol, VoiceChannel, Guild

from .filters import LavapyFilter
from .exceptions import InvalidIdentifier, FilterAlreadyExists, FilterNotApplied
from .node import Node
from .pool import NodePool
from .tracks import Track
from .queue import Queue
from .utils import ClientType

__all__ = ("Player",)

logger = logging.getLogger(__name__)


class Player(VoiceProtocol):
    """
    Lavapy Player object. This subclasses :class:`discord.VoiceProtocol` and such should be treated as one with additions.

    Examples
    --------
    .. code-block:: python

       @commands.command()
       async def connect(self, channel: discord.VoiceChannel):
           voice_client = await channel.connect(cls=lavapy.Player)

    .. warning::
        This class should not be created manually but can be subclassed to add additional functionality. You should instead use :meth:`discord.VoiceChannel.connect()` and pass the player object to the cls kwarg.

    Parameters
    ----------
    client: Union[:class:`discord.Client`, :class:`discord.AutoShardedClient`, :class:`discord.ext.commands.Bot`, :class:`discord.ext.commands.AutoShardedBot`]
        A :class:`discord.Client`, :class:`discord.AutoShardedClient`, :class:`discord.ext.commands.Bot`, :class:`discord.ext.commands.AutoShardedBot`.
    channel: VoiceChannel
        A :class:`discord.VoiceChannel` for the player to connect to.
    """
    def __init__(self, client: ClientType, channel: VoiceChannel) -> None:
        super().__init__(client, channel)
        self.client: ClientType = client
        self.channel: VoiceChannel = channel
        self._node: Optional[Node] = NodePool.getNode()
        self._track: Optional[Track] = None
        self._volume: int = 100
        self._filters: Dict[str, LavapyFilter] = {}
        self._queue: Queue = Queue()
        self._voiceState: Dict[str, Any] = {}
        self._connected: bool = False
        self._paused: bool = False
        self._lastUpdateTime: Optional[datetime.datetime] = None
        self._lastPosition: Optional[float] = None

    def __repr__(self) -> str:
        return f"<Lavapy Player (ChannelID={self.channel.id}) (GuildID={self.guild.id})>"

    @property
    def guild(self) -> Guild:
        """Returns the :class:`discord.Guild`: this player is in."""
        return self.channel.guild

    @property
    def node(self) -> Optional[Node]:
        """Returns the Lavapy :class:`Node` this player is connected to."""
        return self._node

    @property
    def track(self) -> Optional[Track]:
        """Returns the currently playing :class:`Track` if there is one."""
        return self._track

    @property
    def volume(self) -> int:
        """Returns the current volume."""
        return self._volume

    @property
    def filters(self) -> Dict[str, LavapyFilter]:
        """Returns the currently applied :class:`LavapyFilter`s if there are any."""
        return self._filters

    @property
    def queue(self) -> Queue:
        """Returns a :class:`Queue` object which can be used to line up and retrieve tracks."""
        return self._queue

    @property
    def position(self) -> float:
        """Returns the current position of the :class:`Track` in seconds. If nothing is playing, this returns 0."""
        if not self.isPlaying:
            return 0

        if self.isPaused:
            return min(self._lastPosition, self.track.length)

        timeSinceLastUpdate = (datetime.datetime.now(timezone.utc) - self._lastUpdateTime).total_seconds()
        return min(self._lastPosition + timeSinceLastUpdate, self.track.length)

    @property
    def isConnected(self) -> bool:
        """Returns whether the :class:`Player` is connected to a channel or not."""
        return self._connected

    @property
    def isPlaying(self) -> bool:
        """Returns whether the :class:`Player` is currently playing a track or not."""
        return self.isConnected and self.track is not None

    @property
    def isPaused(self) -> bool:
        """Returns whether the :class:`Player` is currently paused or not."""
        return self._paused

    def _updateState(self, state: Dict[str, Any]) -> None:
        """
        Stores the last update time and the last position.

        Parameters
        ----------
        state: Dict[str, Any]
            The raw info sent by Lavalink.
        """
        # State updates are sent in milliseconds so need to be converted to seconds (/1000)
        state: Dict[str, Any] = state.get("state")
        self._lastUpdateTime = datetime.fromtimestamp(state.get("time")/1000, timezone.utc)

        self._lastPosition = state.get("position", 0)/1000

    async def on_voice_server_update(self, data: Dict[str, str]) -> None:
        """|coro|

        Called when the client connects to a voice channel.

        Parameters
        ----------
        data: Dict[str, str]
            The raw info sent by Discord about the voice channel.
        """
        self._voiceState.update({"event": data})
        await self._sendVoiceUpdate()

    async def on_voice_state_update(self, data: Dict[str, Any]) -> None:
        """|coro|

        Called when the client's voice state changes.

        Parameters
        ----------
        data: Dict[str, Any]
            The raw info sent by Discord about the client's voice state.
        """
        self._voiceState.update({"sessionId": data["session_id"]})

        channelID = data["channel_id"]
        if channelID is None:
            # Disconnecting
            self._voiceState.clear()
            return

        channel = self.client.get_channel(channelID)
        if channel != self.channel:
            logger.debug(f"Moved player to channel: {channel.id}")
            self.channel = channel

        await self._sendVoiceUpdate()

    async def _sendVoiceUpdate(self) -> None:
        """|coro|

        Sends data collected from on_voice_server_update and on_voice_state_update to Lavalink.
        """
        if {"sessionId", "event"} == self._voiceState.keys():
            logger.debug(f"Dispatching voice update: {self.channel.id}")

            voiceUpdate = {
                "op": "voiceUpdate",
                "guildId": str(self.guild.id),
                "sessionId": self._voiceState["sessionId"],
                "event": self._voiceState["event"]
            }
            await self.node.send(voiceUpdate)

    async def connect(self, timeout: float, reconnect: bool) -> None:
        """|coro|

        Connects the player to a :class:`discord.VoiceChannel`.

        Parameters
        ----------
        timeout: float
            The timeout for the connection.
        reconnect: bool
            A bool stating if reconnection is expected.
        """
        await self.guild.change_voice_state(channel=self.channel)
        self.node.players.append(self)
        self._connected = True

        logger.info(f"Connected to voice channel: {self.channel.id}")

    async def disconnect(self, *, force: bool = False) -> None:
        """|coro|

        Disconnects the player from a :class:`discord.VoiceChannel.

        Parameters
        ----------
        force: bool
            Whether to force the disconnection. This is currently not used.
        """
        await self.guild.change_voice_state(channel=None)
        self.node.players.remove(self)
        self._connected = False

        logger.info(f"Disconnected from voice channel: {self.channel.id}")

    async def play(self, track: Track, startTime: int = 0, endTime: int = 0, volume: int = 100, replace: bool = True, pause: bool = False) -> None:
        """|coro|

        Plays a given :class:`Track`.

        Parameters
        ----------
        track: Track
            The :class:`Track` to play.
        startTime: int
            The position in milliseconds to start at. By default, this is the beginning.
        endTime: int
            The position in milliseconds to end at. By default, this is the end.
        volume: int
            The volume at which the player should play the track at.
        replace: bool
            A bool stating if the current track should be replaced or not.
        pause: bool
            A bool stating if the track should start paused.
        """
        if self.isPlaying and not replace:
            return
        newTrack = {
            "op": "play",
            "guildId": str(self.guild.id),
            "track": track.id,
            "startTime": str(startTime),
            "volume": str(volume),
            "noReplace": not replace,
            "pause": pause
        }
        if endTime > 0:
            newTrack["endTime"] = str(endTime)
        self._track = track
        self._volume = volume
        await self.node.send(newTrack)

        logger.debug(f"Started playing track: {self.track.title} in {self.channel.id}")

    async def stop(self) -> None:
        """|coro|

        Stops the currently playing :class:`Track`.
        """
        stop = {
            "op": "stop",
            "guildId": str(self.guild.id)
        }
        tempTrack = self.track
        self._track = None
        await self.node.send(stop)

        logger.debug(f"Stopped playing track: {tempTrack.title} in {self.channel.id}")

    async def pause(self) -> None:
        """|coro|

        Pauses the :class:`Player` if it was playing.
        """
        await self._togglePause(True)

    async def resume(self) -> None:
        """|coro|

        Resumes the :class:`Player` if it was paused.
        """
        await self._togglePause(False)

    async def _togglePause(self, pause: bool) -> None:
        """|coro|

        Toggles the player's pause state.

        Parameters
        ----------
        pause: bool
            A bool stating whether the player's paused state should be True or False.
        """
        pause = {
            "op": "pause",
            "guildId": str(self.guild.id),
            "pause": pause
        }
        self._paused = pause
        await self.node.send(pause)

        logger.debug(f"Toggled pause: {pause} in {self.channel.id}")

    async def seek(self, position: int) -> None:
        """|coro|

        Seek to a given position.

        Parameters
        ----------
        position: int
            The position to seek to.

        Raises
        ------
        InvalidIdentifier
            Seek position is bigger than the track length.
        """
        if position > self.track.length:
            raise InvalidIdentifier("Seek position is bigger than track length.")
        seek = {
            "op": "seek",
            "guildId": str(self.guild.id),
            "position": position
        }
        await self.node.send(seek)

        logger.debug(f"Seeked to position: {position}")

    async def setVolume(self, volume: int) -> None:
        """|coro|

        Changes the :class:`Player`'s volume.

        Parameters
        ----------
        volume: int
            The new volume.
        """
        self._volume = max(min(volume, 1000), 0)
        volume = {
            "op": "volume",
            "guildId": str(self.guild.id),
            "volume": self.volume
        }
        await self.node.send(volume)

        logger.debug(f"Set volume to: {volume}")

    async def moveTo(self, channel: VoiceChannel) -> None:
        """|coro|

        Moves the player to another :class:`discord.VoiceChannel`.

        Parameters
        ----------
        channel: VoiceChannel
            The :class:`VoiceChannel` to move to.
        """
        await self.guild.change_voice_state(channel=channel)

    async def addFilter(self, filter: LavapyFilter) -> None:
        """|coro|

        Adds a :class:`LavapyFilter` to the player.

        .. warning::
            This requires Lavalink 3.4 or greater..

        Parameters
        ----------
        filter: LavapyFilter
            The :class:`LavapyFilter` to apply to the player.

        Raises
        ------
        FilterAlreadyExists
            The specific :class:`LavapyFilter` is already applied.
        """
        name = filter.name
        if filter.name in self.filters.keys():
            raise FilterAlreadyExists(f"Filter <{name}> is already applied. Please remove it first.")

        self.filters[name] = filter
        await self._updateFilters()

        logger.debug(f"Added filter: {name} with payload {filter.payload}")

    async def removeFilter(self, filter: Union[LavapyFilter, Type[LavapyFilter]]) -> None:
        """|coro|

        Removes a :class:`LavapyFilter` based on its name.

        .. warning::
            This requires Lavalink 3.4 or greater.

        Parameters
        ----------
        filter: Union[LavapyFilter, Type[LavapyFilter]]
            The :class`LavapyFilter` to remove. This can either be a non-initialised class like `lavapy.Equalizer` or an initialised one like `lavapy.Equalizer.flat()`.

        Raises
        ------
        FilterNotApplied
            The specific :class:`LavapyFilter` is not applied.
        """
        name = filter.name
        if name not in self.filters.keys():
            raise FilterNotApplied(f"{name} is not applied.")

        del self.filters[name]
        await self._updateFilters()

        logger.debug(f"Removed filter: {name}")

    async def _updateFilters(self) -> None:
        """|coro|

        Collects all applied filters and sends them to Lavalink.
        """
        filterPayload = {
            "op": "filters",
            "guildId": str(self.guild.id),
            "volume": self.volume/100,
        }
        for key, value in self.filters.items():
            filterPayload[value.name] = value.payload
        await self.node.send(filterPayload)

# async def destroy(self) -> None:
#     destroy = {
#         "op": "destroy",
#         "guildId": str(self.guild.id)
#     }
#     await self.node.send(destroy)
