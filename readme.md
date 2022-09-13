* Merged with upstream of commit 521f482 on Sep 2, 2022 (release 0.5.12)

### change metadata to get real title and artist
- if no tag, find title / artist from meta title
- support meta title formats: %n.%p-%t, %n.%t--%p, %n.%t, %p-%t, %t--%p, %t
- default download changes to download best match first
- download add ignore path by key 'Download/ignore-path' in osdlyrics.conf

### modified:
- 增加：     readme.md
- 修改：     po/zh_CN.po
- 修改：     src/ol_lyric_candidate_selector.c
- 修改：     src/ol_lyric_source.c
- 修改：     src/ol_main.c
- 修改：     src/ol_metadata.c
- 修改：     src/ol_metadata.h
- 修改：     src/ol_player.c

### install instruction:
- ./autogen.sh
- ./configure --prefix=/usr PYTHON=/usr/bin/python3
- make
- sudo make install
- sudo mv /usr/lib/python3.10/site-packages/osdlyrics /usr/lib/python3/dist-packages

### uninstall instruction:
- sudo make uninstall
- sudo rm -rf /usr/share/osdlyrics
- sudo rm -rf /usr/lib/osdlyrics
- sudo rm -rf /usr/lib/python3/dist-package/osdlyrics

### dependencies: (ubuntu20.04)
- autoconf automake libtool
- libglib2.0-dev
- libgtk2.0-dev
- libdbus-glib-1-dev
- libnotify-dev
- intltool
- libappindicator-dev
- python3-future
