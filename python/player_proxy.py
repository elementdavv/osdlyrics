# -*- coding: utf-8 -*-
#
# Copyright (C) 2011  Tiger Soldier
#
# This file is part of OSD Lyrics.
#
# OSD Lyrics is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OSD Lyrics is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OSD Lyrics.  If not, see <https://www.gnu.org/licenses/>.
#
from __future__ import unicode_literals
from builtins import object, super
from future.utils import raise_from

from abc import abstractmethod
import logging

import dbus
import dbus.service

from . import errors, timer
from .app import App
from .consts import (MPRIS2_PLAYER_INTERFACE, PLAYER_PROXY_INTERFACE,
                     PLAYER_PROXY_OBJECT_PATH_PREFIX)
from .dbusext.service import Object as DBusObject, property as dbus_property


class CAPS(object):
    NEXT = 1 << 0
    PREV = 1 << 1
    PAUSE = 1 << 2
    PLAY = 1 << 3
    SEEK = 1 << 4
    PROVIDE_METADATA = 1 << 5


class REPEAT(object):
    NONE = 0
    TRACK = 1
    ALL = 2


class STATUS(object):
    PLAYING = 0
    PAUSED = 1
    STOPPED = 2


class ConnectPlayerError(errors.BaseError):
    """
    Exception raised when BasePlayerProxy.do_connect_player() fails
    """
    pass


class BasePlayerProxy(dbus.service.Object):
    """ Base class to create an application to provide player proxy support
    """

    def __init__(self, name):
        """

        Arguments:
        - `name`: The suffix of the bus name. The full bus name is
          `org.osdlyrics.PlayerProxy.` + name
        """
        self._app = App('PlayerProxy.' + name)
        super().__init__(conn=self._app.connection,
                         object_path=PLAYER_PROXY_OBJECT_PATH_PREFIX + name)
        self._name = name
        self._connected_players = {}

    @property
    def name(self):
        return self._name

    def run(self):
        self._app.run()

    @dbus.service.method(dbus_interface=PLAYER_PROXY_INTERFACE,
                         in_signature='',
                         out_signature='aa{sv}')
    def ListActivePlayers(self):
        return [player.to_dict() for player in self.do_list_active_players()]

    @dbus.service.method(dbus_interface=PLAYER_PROXY_INTERFACE,
                         in_signature='',
                         out_signature='aa{sv}')
    def ListSupportedPlayers(self):
        return [player.to_dict() for player in self.do_list_supported_players()]

    @dbus.service.method(dbus_interface=PLAYER_PROXY_INTERFACE,
                         in_signature='',
                         out_signature='aa{sv}')
    def ListActivatablePlayers(self):
        return [player.to_dict() for player in
                self.do_list_activatable_players()]

    @dbus.service.method(dbus_interface=PLAYER_PROXY_INTERFACE,
                         in_signature='s',
                         out_signature='o')
    def ConnectPlayer(self, player_name):
        if self._connected_players.setdefault(player_name, None):
            return self._connected_players[player_name].object_path
        try:
            player = self.do_connect_player(player_name)
        except TypeError as e:
            raise_from(errors.BaseError(
                '%s cannot instantiate Player[%s, %s]' % (type(self).__name__, self.name, player_name)
            ), e)
        if player and player.connected:
            player.set_disconnect_cb(self._player_lost_cb)
            self._connected_players[player_name] = player
            logging.info('Connected to %s', player.object_path)
            return player.object_path
        else:
            raise ConnectPlayerError('%s cannot be connected', player_name)

    @dbus.service.signal(dbus_interface=PLAYER_PROXY_INTERFACE,
                         signature='s')
    def PlayerLost(self, player_name):
        pass

    def _player_lost_cb(self, player):
        if player.name in self._connected_players:
            del self._connected_players[player.name]
            self.PlayerLost(player.name)

    @abstractmethod
    def do_list_active_players(self):
        """
        Lists supported players that are aready running

        Returns an list of `PlayerInfo` objects.
        """
        raise NotImplementedError()

    @abstractmethod
    def do_list_supported_players(self):
        """
        Lists supported players.

        Returns an list of `PlayerInfo` objects.
        """
        raise NotImplementedError()

    @abstractmethod
    def do_list_activatable_players(self):
        """
        Lists supported players installed on the system.

        Returns an list of `PlayerInfo` objects.
        """
        raise NotImplementedError()

    def do_connect_player(self, playername):
        """
        Creates an Player object according to playername.

        Returns the created `BasePlayer` object, or None if cannot connect to
        the player with `playername`.
        """
        raise NotImplementedError()


class PlayerInfo(object):
    """Information about a supported player
    """

    def __init__(self, name, appname='', binname='', cmd='', icon=''):
        self._name = name
        self._appname = appname
        self._binname = binname
        self._cmd = cmd
        self._icon = icon

    @classmethod
    def from_name(cls, name):
        return cls(name, icon=name)

    @property
    def name(self):
        return self._name

    @property
    def appname(self):
        return self._appname

    @property
    def binname(self):
        return self._binname

    @property
    def cmd(self):
        return self._cmd

    @property
    def icon(self):
        return self._icon

    def to_dict(self):
        """
        Converts the PlayerInfo object to an dict that fits the specification
        """
        keys = ['name', 'appname', 'binname', 'cmd', 'icon']
        ret = {}
        for k in keys:
            ret[k] = getattr(self, '_' + k)
        return ret


class BasePlayer(DBusObject):
    """ Base class of a player

    Derived classes MUST reimplement following methods:

    - `get_metadata`
    - `get_position`
    - `get_caps`

    Derived classes SHOULD reimplement following methods if supported.
    - `get_status`
    - `get_repeat`
    - `set_repeat`
    - `get_shuffle`
    - `set_shuffle`
    - `play`
    - `pause`
    - `prev`
    - `next`
    - `set_position`
    - `set_volume`
    - `get_volume`
    """

    def __init__(self, proxy, name):
        """

        Arguments:
        - `proxy`: The BasePlayerProxy object that creates the player
        - `name`: The name of the player object
        """
        self._object_path = PLAYER_PROXY_OBJECT_PATH_PREFIX + proxy.name + '/' + name
        super().__init__(conn=proxy.connection,
                         object_path=self._object_path)
        self._name = name
        self._proxy = proxy
        self._disconnect_cb = None
        self._connected = True
        self._timer = None
        self._status = None
        self._loop_status = None
        self._metadata = None
        self._current_trackid = 0
        self._caps = None
        self._shuffle = None

    def set_disconnect_cb(self, disconnect_cb):
        self._disconnect_cb = disconnect_cb

    @property
    def name(self):
        return self._name

    @property
    def proxy(self):
        return self._proxy

    def disconnect(self):
        if self._connected:
            self._connected = False
            self.remove_from_connection()
            if callable(self._disconnect_cb):
                self._disconnect_cb(self)

    def get_status(self):
        """
        Return the playing status.

        The return value should be one of STATUS.PLAYING, STATUS.PAUSED, and
        STATUS.STOPPED

        Derived classes that supports playing status should reimplement this.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_metadata(self):
        # type: () -> Metadata
        """
        Return metadata of current track. The return value is of the type Metadata
        """
        raise NotImplementedError()

    @abstractmethod
    def get_position(self):
        """
        Gets the ellapsed time in current track.

        Returns the time in milliseconds.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_caps(self):
        """
        Return capablities of the players.

        The return value should be a set of CAPS.PLAY, CAPS.PAUSE, CAPS.NEXT,
        CAPS.PREV, CAPS.SEEK
        """
        raise NotImplementedError()

    def get_repeat(self):
        """
        Gets the repeat mode of the player

        Returns one of REPEAT.NONE, REPEAT.TRACK, or REPEAT.ALL

        The default implementation returns REPEAT.NONE
        """
        return REPEAT.NONE

    def set_repeat(self, mode):
        """
        Sets the repeat mode of the player

        Arguments:
        - `mode`: REPEAT.NONE, REPEAT.TRACK, or REPEAT.ALL
        """
        raise NotImplementedError()

    def get_shuffle(self):
        """
        Gets the shuffle mode of the player

        Returns True if the playlist is shuffle, or False otherwise.

        The default implementation returns False
        """
        return False

    def set_shuffle(self, shuffle):
        """
        Set whether the tracks in track list should be played randomly.

        Arguments:
        - `shuffle`: boolean, True if shuffle
        """
        raise NotImplementedError()

    def play(self):
        """
        Start/continue playing the current track
        """
        raise NotImplementedError()

    def pause(self):
        """
        Pause the current track
        """
        raise NotImplementedError()

    def stop(self):
        """
        Stop playing.
        """
        raise NotImplementedError()

    def prev(self):
        """
        Play the previous track.
        """
        raise NotImplementedError()

    def next(self):
        """
        Play the next track.
        """
        raise NotImplementedError()

    def set_position(self, pos):
        """
        Seek to the given position.

        Arguments:
        - `pos`: Seek time in millisecond
        """
        raise NotImplementedError()

    def get_volume(self):
        """
        Gets the volume of the player.

        Return the volume in the range of [0.0, 1.0]
        """
        raise NotImplementedError()

    def set_volume(self, volume):
        """
        Sets the volume of the player.

        Arguments:
        - `volume`: volume in the range of [0.0, 1.0]
        """
        raise NotImplementedError()

    def _setup_timer_status(self, status):
        status_map = {
            STATUS.PAUSED: 'pause',
            STATUS.PLAYING: 'play',
            STATUS.STOPPED: 'stop',
        }
        if self._timer:
            getattr(self._timer, status_map[status])()

    def _setup_timer(self):
        if self._timer is None:
            self._timer = timer.Timer()
            self._setup_timer_status(self._get_cached_status())

    def _get_cached_position(self):
        """
        Get the current position from cached timer if possible
        """
        if self._timer is None:
            self._setup_timer()
            if self._get_cached_status() != STATUS.STOPPED:
                self._timer.time = self.get_position()
        return self._timer.time

    def _get_cached_loop_status(self):
        if self._loop_status is None:
            self._loop_status = self.get_repeat()
        return self._loop_status

    def _get_cached_status(self):
        if self._status is None:
            self._status = self.get_status()
        return self._status

    def _get_cached_metadata(self):
        if self._metadata is None:
            self._metadata = self._make_metadata(self.get_metadata())
        return self._metadata

    def _make_metadata(self, metadata):
        dct = metadata.to_mpris2()
        dct['mpris:trackid'] = self._get_current_trackid()
        return dct

    def _get_current_trackid(self):
        return '/%s' % self._current_trackid

    def _get_cached_caps(self):
        if self._caps is None:
            self._caps = self.get_caps()
        return self._caps

    def _get_cached_shuffle(self):
        if self._shuffle is None:
            self._shuffle = self.get_shuffle()
        return self._shuffle

    @property
    def connected(self):
        return self._connected

    @property
    def object_path(self):
        return self._object_path

    @dbus.service.method(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                         in_signature='',
                         out_signature='')
    def Next(self):
        self.next()

    @dbus.service.method(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                         in_signature='',
                         out_signature='')
    def Previous(self):
        self.prev()

    @dbus.service.method(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                         in_signature='',
                         out_signature='')
    def Pause(self):
        self.pause()

    @dbus.service.method(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                         in_signature='',
                         out_signature='')
    def Stop(self):
        self.stop()

    @dbus.service.method(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                         in_signature='',
                         out_signature='')
    def Play(self):
        self.play()

    @dbus.service.method(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                         in_signature='x',
                         out_signature='')
    def Seek(self, offset):
        pos = self._get_cached_position()
        pos += offset // 1000
        if pos < 0:
            pos = 0
        self.set_position(pos)

    @dbus.service.method(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                         in_signature='ox',
                         out_signature='')
    def SetPosition(self, trackid, position):
        if trackid != self._get_current_trackid():
            return
        self.set_position(position // 1000)

    @dbus.service.method(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                         in_signature='',
                         out_signature='')
    def PlayPause(self):
        if hasattr(self, 'play_pause'):
            self.play_pause()
        else:
            status = self._get_cached_status()
            if status == STATUS.PLAYING:
                self.pause()
            else:
                self.play()

    @dbus.service.method(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                         in_signature='s',
                         out_signature='')
    def OpenUri(self, uri):
        self.open_uri(uri)

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='s',
                   writeable=False)
    def PlaybackStatus(self):
        status_map = {
            STATUS.PLAYING: 'Playing',
            STATUS.PAUSED: 'Paused',
            STATUS.STOPPED: 'Stopped',
        }
        return status_map[self._get_cached_status()]

    @PlaybackStatus.setter
    def PlaybackStatus(self, status):
        self._status = status

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='s')
    def LoopStatus(self):
        status_map = {
            REPEAT.NONE: 'None',
            REPEAT.ALL: 'Playlist',
            REPEAT.TRACK: 'Track',
        }
        return status_map[self._get_cached_loop_status()]

    @LoopStatus.setter
    def LoopStatus(self, loop_status):
        self._loop_status = loop_status

    @LoopStatus.dbus_setter
    def LoopStatus(self, loop_status):
        status_map = {
            'None': REPEAT.NONE,
            'Playlist': REPEAT.ALL,
            'Track': REPEAT.TRACK,
        }
        if loop_status not in status_map:
            raise ValueError('Unknown loop status ' + loop_status)
        self.set_repeat(status_map[loop_status])

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='d')
    def Rate(self):
        return 1.0

    @Rate.setter
    def Rate(self, rate):
        pass

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='b')
    def Shuffle(self):
        return self._get_cached_shuffle()

    @Shuffle.setter
    def Shuffle(self, shuffle):
        self._shuffle = shuffle

    @Shuffle.dbus_setter
    def Shuffle(self, shuffle):
        self.set_shuffle(shuffle)

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='a{sv}',
                   writeable=False)
    def Metadata(self):
        return self._get_cached_metadata()

    @Metadata.setter
    def Metadata(self, metadata):
        self._metadata = metadata

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='d')
    def Volume(self):
        return self.get_volume()

    @Volume.dbus_setter
    def Volume(self, volume):
        if volume < 0.0:
            volume = 0.0
        if volume > 1.0:
            volume = 1.0
        self.set_volume(volume)

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='x')
    def Position(self):
        return self._get_cached_position()

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='d')
    def MinimumRate(self):
        return 1.0

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='d')
    def MaximumRate(self):
        return 1.0

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='b',
                   writeable=False)
    def CanGoNext(self):
        return CAPS.NEXT in self._get_cached_caps()

    @CanGoNext.setter
    def CanGoNext(self, value):
        pass

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='b',
                   writeable=False)
    def CanGoPrevious(self):
        return CAPS.PREV in self._get_cached_caps()

    @CanGoPrevious.setter
    def CanGoPrevious(self, value):
        pass

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='b',
                   writeable=False)
    def CanPlay(self):
        return CAPS.PLAY in self._get_cached_caps()

    @CanPlay.setter
    def CanPlay(self, value):
        pass

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='b',
                   writeable=False)
    def CanPause(self):
        return CAPS.PAUSE in self._get_cached_caps()

    @CanPause.setter
    def CanPause(self, value):
        pass

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='b',
                   writeable=False)
    def CanSeek(self):
        return CAPS.SEEK in self._get_cached_caps()

    @CanSeek.setter
    def CanSeek(self, value):
        pass

    @dbus_property(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                   type_signature='b')
    def CanControl(self):
        return True

    @dbus.service.signal(dbus_interface=MPRIS2_PLAYER_INTERFACE,
                         signature='x')
    def Seeked(self, position):
        pass

    def track_changed(self, metadata=None):
        self._current_trackid += 1
        if self._timer is not None:
            self._timer.time = self.get_position()
        if metadata is None:
            metadata = self.get_metadata()
        self.Metadata = self._make_metadata(metadata)

    def status_changed(self):
        """
        Notify that the playing status has been changed.
        """
        status = self.get_status()
        self._setup_timer_status(status)
        self.PlaybackStatus = status

    def repeat_changed(self):
        """
        Notify the repeat mode has been changed.
        """
        self.LoopStatus = self.get_repeat()

    def shuffle_changed(self):
        """
        Notify the shuffle mode has been changed.
        """
        self.Shuffle = self.get_shuffle()

    def caps_changed(self):
        """
        Notify the capability of the player has been changed.
        """
        orig_caps = self._caps
        self._caps = self.get_caps()
        if orig_caps is not None:
            caps_map = {
                CAPS.NEXT: 'CanGoNext',
                CAPS.PREV: 'CanGoPrevious',
                CAPS.PLAY: 'CanPlay',
                CAPS.PAUSE: 'CanPause',
                CAPS.SEEK: 'CanSeek',
            }
            for cap, method in caps_map.items():
                if cap in orig_caps != cap in self._caps:
                    setattr(self, method, cap in self._caps)

    def position_changed(self, position):
        """
        Notify that the position has been changed
        """
        if self._timer is not None:
            self._timer.time = position
        self.Seeked(position * 1000)
