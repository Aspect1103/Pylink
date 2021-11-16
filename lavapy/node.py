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

import logging
import aiohttp
from aiohttp import ClientResponse
from typing import TYPE_CHECKING, Optional, Union, Tuple, List, Dict, Type, Any

import discord.ext

from .exceptions import WebsocketAlreadyExists, BuildTrackError, LavalinkException, LoadTrackError
from .tracks import Track
from .websocket import Websocket

if TYPE_CHECKING:
    from .player import Player
    from .tracks import Playable, PartialResource, MultiTrack
    from .utils import Stats
    from .ext.spotify.client import SpotifyClient
    from .ext.spotify.tracks import SpotifyPlayable

__all__ = ("Node",)

logger = logging.getLogger(__name__)


class Node:
    """
    Lavapy Node object.

    .. warning::
        This class should not be created manually. Please use :meth:`NodePool.createNode()` instead.
    """
    def __init__(self, client: Union[discord.Client, discord.AutoShardedClient, discord.ext.commands.Bot, discord.ext.commands.AutoShardedBot], host: str, port: int, password: str, region: Optional[discord.VoiceRegion], spotifyClient: Optional[SpotifyClient], identifier: str) -> None:
        self._client: Union[discord.Client, discord.AutoShardedClient, discord.ext.commands.Bot, discord.ext.commands.AutoShardedBot] = client
        self._host: str = host
        self._port: int = port
        self._password: str = password
        self._region: Optional[discord.VoiceRegion] = region
        self._spotifyClient: SpotifyClient = spotifyClient
        self._identifier: str = identifier
        self._players: List[Player] = []
        self._stats: Optional[Stats] = None
        self._session: aiohttp.ClientSession = aiohttp.ClientSession()
        self._websocket: Optional[Websocket] = None

    def __repr__(self) -> str:
        return f"<Lavapy Node (Domain={self.host}:{self.port}) (Identifier={self.identifier}) (Region={self.region}) (Players={len(self.players)})>"

    @property
    def client(self) -> Union[discord.Client, discord.AutoShardedClient, discord.ext.commands.Bot, discord.ext.commands.AutoShardedBot]:
        """Returns the client or bot object assigned to this node."""
        return self._client

    @property
    def host(self) -> str:
        """Returns the IP address of the Lavalink server."""
        return self._host

    @property
    def port(self) -> int:
        """Returns the port of the Lavalink server."""
        return self._port

    @property
    def password(self) -> str:
        """Returns the password to the Lavalink server."""
        return self._password

    @property
    def region(self) -> discord.VoiceRegion:
        """Returns the voice region assigned to this node."""
        return self._region

    @property
    def spotifyClient(self) -> Optional[SpotifyClient]:
        """Returns the Spotify client associated with this node if there is one."""
        return self._spotifyClient

    @property
    def identifier(self) -> str:
        """Returns the unique identifier for this node."""
        return self._identifier

    @property
    def players(self) -> List[Player]:
        """Returns a list of all Lavapy player objects which are connected to this node."""
        return self._players

    @property
    def stats(self) -> Optional[Stats]:
        """Returns useful information sent by Lavalink about this node."""
        return self._stats

    @property
    def session(self) -> aiohttp.client.ClientSession:
        """Returns the session used for sending and getting data."""
        return self._session

    async def connect(self) -> None:
        """|coro|

        Initialises the websocket connection to the Lavalink server.

        Raises
        ------
        WebsocketAlreadyExists
            The websocket for this node already exists.
        """
        logger.debug(f"Connecting to the Lavalink server at: {self.host}:{self.port}")
        if self._websocket is None:
            self._websocket = Websocket(self)
        else:
            raise WebsocketAlreadyExists("Websocket already initialised.")

    async def disconnect(self, *, force: bool = False) -> None:
        """|coro|

        Disconnects this :class:`Node` and removes it from the :class:`NodePool`.

        Parameters
        ----------
        force: bool
            Whether to force the disconnection. This is currently not used.
        """
        for player in self.players:
            await player.disconnect(force=force)

        self._websocket.listener.cancel()
        await self._websocket.connection.close()

    async def _getData(self, endpoint: str, params: Dict[str, str]) -> Tuple[Dict[str, Any], ClientResponse]:
        """|coro|

        Make a request to Lavalink with a given endpoint and return a response.

        Parameters
        ----------
        endpoint: str
            The endpoint to query from Lavalink.
        params: Dict[str, str]
            A dict containing additional info to send to Lavalink.

        Returns
        -------
        Tuple[Dict[str, Any], :class:`aiohttp.ClientResponse`]
            A tuple containing the response from Lavalink as well as the websocket response to determine the status of the request.
        """
        logger.debug(f"Getting endpoint {endpoint} with data {params}")
        headers = {
            "Authorization": self.password
        }
        async with await self.session.get(f"http://{self.host}:{self.port}/{endpoint}", headers=headers, params=params) as req:
            data = await req.json()
        return data, req

    async def _send(self, payload: Dict[str, Any]) -> None:
        """|coro|

        Send a payload to Lavalink without a response.

        Parameters
        ----------
        payload: Dict[str, Any]
            The payload to send to Lavalink.
        """
        logger.debug(f"Sending payload: {payload}")
        await self._websocket.connection.send_json(payload)

    async def buildTrack(self, id: str) -> Track:
        """|coro|

        Builds a :class:`Track` from a base64 track ID.

        Parameters
        ----------
        id: str
            The base64 track ID.

        Raises
        ------
        BuildTrackError
            An error occurred while building the track.

        Returns
        -------
        Track
            A Lavapy track object.
        """
        track, response = await self._getData("decodetrack", {"track": id})
        if response.status != 200:
            raise BuildTrackError("A error occurred while building the track.", track)
        return Track(id, track)

    async def getTracks(self, cls: Union[Type[Playable], Type[SpotifyPlayable]], query: str) -> Optional[Union[Track, List[Track], MultiTrack]]:
        """|coro|

        Gets data about a :class:`Track` or :class:`MultiTrack` from Lavalink.

        Parameters
        ----------
        cls: Union[Type[Playable], Type[SpotifyPlayable]]
            The Lavapy resource to create an instance of.
        query: str
            The query to search for via Lavalink.

        Returns
        -------
        Optional[Union[Track, List[Track], MultiTrack]]
            A Lavapy resource which can be used to play music.
        """
        logger.info(f"Getting data with query: {query}")
        data, response = await self._getData("loadtracks", {"identifier": query})
        if response.status != 200:
            raise LavalinkException("Invalid response from lavalink.")

        loadType = data.get("loadType")
        if loadType == "LOAD_FAILED":
            raise LoadTrackError(f"Track failed to load with data: {data}.")
        elif loadType == "NO_MATCHES":
            return None
        elif loadType == "TRACK_LOADED":
            trackInfo = data["tracks"][0]
            # noinspection PyTypeChecker
            return cls(trackInfo["track"], trackInfo["info"])
        elif loadType == "SEARCH_RESULT":
            # noinspection PyTypeChecker
            return [cls(element["track"], element["info"]) for element in data["tracks"]]
        elif loadType == "PLAYLIST_LOADED":
            playlistInfo = data["playlistInfo"]
            # noinspection PyTypeChecker
            return cls(playlistInfo["name"], [cls._trackCls(track["track"], track["info"]) for track in data["tracks"]])

    async def processPartialResource(self, partial: PartialResource) -> Track:
        """|coro|

        Processes a :class:`PartialResource` and returns the actual data.

        Parameters
        ----------
        partial: PartialResource
            The partial resource to get details on.

        Returns
        -------
        Track
            A Lavapy track object which can be used to play music.
        """
        temp = await self.getTracks(partial.cls, partial.query)
        return temp[0]
