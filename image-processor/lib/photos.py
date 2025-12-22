"""
Photos.app Library Access

Accesses Photos library database to list images, albums, and retrieve file paths.
Follows same SQLite pattern as imessage-core for database access.

Requires: Full Disk Access permission in System Settings > Privacy & Security
"""
import sqlite3
import os
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

# Photos.app database and library locations
PHOTOS_LIBRARY = os.path.expanduser('~/Pictures/Photos Library.photoslibrary')
PHOTOS_DB = os.path.join(PHOTOS_LIBRARY, 'database', 'Photos.sqlite')

# Core Data epoch (Jan 1, 2001) offset from Unix epoch
CORE_DATA_EPOCH = 978307200


@dataclass
class PhotoInfo:
    """Information about a photo in the library."""
    uuid: str
    filename: str
    original_filename: str
    directory: str
    file_path: str
    date_created: Optional[datetime]
    date_modified: Optional[datetime]
    width: int
    height: int
    file_size: int
    kind: str  # 'image', 'video', etc.
    is_favorite: bool
    is_hidden: bool
    album_names: List[str]

    def __str__(self):
        date_str = self.date_created.strftime('%Y-%m-%d %H:%M') if self.date_created else 'Unknown'
        return f"{self.filename} ({self.width}x{self.height}) - {date_str}"


@dataclass
class AlbumInfo:
    """Information about a Photos album."""
    uuid: str
    title: str
    photo_count: int
    kind: int  # Album type


class PhotosLibrary:
    """Access to Photos.app library via SQLite."""

    def __init__(self, library_path: str = None):
        """
        Initialize Photos library access.

        Args:
            library_path: Path to Photos library. If None, uses default location.

        Raises:
            FileNotFoundError: If Photos library or database not found.
        """
        self.library_path = library_path or PHOTOS_LIBRARY
        self.db_path = os.path.join(self.library_path, 'database', 'Photos.sqlite')

        if not os.path.exists(self.library_path):
            raise FileNotFoundError(
                f"Photos library not found: {self.library_path}\n"
                f"Make sure Photos.app has been used on this Mac."
            )

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"Photos database not found: {self.db_path}\n"
                f"The library may be corrupted or in an unsupported format."
            )

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        # Read-only connection to avoid any issues
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.OperationalError as e:
            if "unable to open database file" in str(e):
                raise PermissionError(
                    f"Cannot access Photos database: {self.db_path}\n\n"
                    f"This requires Full Disk Access permission.\n"
                    f"Go to: System Settings > Privacy & Security > Full Disk Access\n"
                    f"And enable access for the application running this script.\n\n"
                    f"Note: If running from Terminal or an IDE, you need to grant\n"
                    f"Full Disk Access to that specific application."
                ) from e
            raise

    def _convert_timestamp(self, core_data_ts: float) -> Optional[datetime]:
        """Convert Core Data timestamp to datetime."""
        if core_data_ts is None or core_data_ts == 0:
            return None
        try:
            unix_ts = core_data_ts + CORE_DATA_EPOCH
            return datetime.fromtimestamp(unix_ts)
        except (ValueError, OSError):
            return None

    def list_albums(self, limit: int = 50) -> List[AlbumInfo]:
        """
        List available albums.

        Args:
            limit: Maximum number of albums to return.

        Returns:
            List of AlbumInfo objects.
        """
        conn = self._connect()
        try:
            c = conn.cursor()
            # ZKIND: 2 = regular album, 1505 = smart album, etc.
            c.execute('''
                SELECT
                    ZUUID,
                    ZTITLE,
                    ZKIND,
                    (SELECT COUNT(*) FROM Z_28ASSETS WHERE Z_28ALBUMS = ZGENERICALBUM.Z_PK) as photo_count
                FROM ZGENERICALBUM
                WHERE ZTITLE IS NOT NULL
                  AND ZTRASHEDSTATE = 0
                  AND ZKIND IN (2, 1505, 3999)
                ORDER BY ZTITLE
                LIMIT ?
            ''', (limit,))

            albums = []
            for row in c.fetchall():
                albums.append(AlbumInfo(
                    uuid=row['ZUUID'],
                    title=row['ZTITLE'],
                    photo_count=row['photo_count'] or 0,
                    kind=row['ZKIND']
                ))
            return albums
        finally:
            conn.close()

    def get_recent_photos(self, limit: int = 10) -> List[PhotoInfo]:
        """
        Get most recent photos from library.

        Args:
            limit: Maximum number of photos to return.

        Returns:
            List of PhotoInfo objects, newest first.
        """
        conn = self._connect()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT
                    ZUUID,
                    ZFILENAME,
                    ZORIGINALFILENAME,
                    ZDIRECTORY,
                    ZDATECREATED,
                    ZMODIFICATIONDATE,
                    ZWIDTH,
                    ZHEIGHT,
                    ZKIND,
                    ZFAVORITE,
                    ZHIDDEN,
                    ZTRASHEDSTATE
                FROM ZASSET
                WHERE ZTRASHEDSTATE = 0
                  AND ZKIND = 0
                ORDER BY ZDATECREATED DESC
                LIMIT ?
            ''', (limit,))

            photos = []
            for row in c.fetchall():
                file_path = self._resolve_photo_path(
                    row['ZUUID'],
                    row['ZDIRECTORY'],
                    row['ZFILENAME']
                )
                photos.append(PhotoInfo(
                    uuid=row['ZUUID'],
                    filename=row['ZFILENAME'] or '',
                    original_filename=row['ZORIGINALFILENAME'] or '',
                    directory=row['ZDIRECTORY'] or '',
                    file_path=file_path,
                    date_created=self._convert_timestamp(row['ZDATECREATED']),
                    date_modified=self._convert_timestamp(row['ZMODIFICATIONDATE']),
                    width=row['ZWIDTH'] or 0,
                    height=row['ZHEIGHT'] or 0,
                    file_size=0,  # Would need additional query
                    kind='image',
                    is_favorite=bool(row['ZFAVORITE']),
                    is_hidden=bool(row['ZHIDDEN']),
                    album_names=[]
                ))
            return photos
        finally:
            conn.close()

    def get_photos_by_date(self, since: datetime = None, until: datetime = None,
                           limit: int = 25) -> List[PhotoInfo]:
        """
        Get photos within a date range.

        Args:
            since: Start date (inclusive).
            until: End date (inclusive).
            limit: Maximum number of photos.

        Returns:
            List of PhotoInfo objects.
        """
        conn = self._connect()
        try:
            c = conn.cursor()

            query = '''
                SELECT
                    ZUUID,
                    ZFILENAME,
                    ZORIGINALFILENAME,
                    ZDIRECTORY,
                    ZDATECREATED,
                    ZMODIFICATIONDATE,
                    ZWIDTH,
                    ZHEIGHT,
                    ZKIND,
                    ZFAVORITE,
                    ZHIDDEN
                FROM ZASSET
                WHERE ZTRASHEDSTATE = 0
                  AND ZKIND = 0
            '''
            params = []

            if since:
                since_ts = since.timestamp() - CORE_DATA_EPOCH
                query += ' AND ZDATECREATED >= ?'
                params.append(since_ts)

            if until:
                until_ts = until.timestamp() - CORE_DATA_EPOCH
                query += ' AND ZDATECREATED <= ?'
                params.append(until_ts)

            query += ' ORDER BY ZDATECREATED DESC LIMIT ?'
            params.append(limit)

            c.execute(query, params)

            photos = []
            for row in c.fetchall():
                file_path = self._resolve_photo_path(
                    row['ZUUID'],
                    row['ZDIRECTORY'],
                    row['ZFILENAME']
                )
                photos.append(PhotoInfo(
                    uuid=row['ZUUID'],
                    filename=row['ZFILENAME'] or '',
                    original_filename=row['ZORIGINALFILENAME'] or '',
                    directory=row['ZDIRECTORY'] or '',
                    file_path=file_path,
                    date_created=self._convert_timestamp(row['ZDATECREATED']),
                    date_modified=self._convert_timestamp(row['ZMODIFICATIONDATE']),
                    width=row['ZWIDTH'] or 0,
                    height=row['ZHEIGHT'] or 0,
                    file_size=0,
                    kind='image',
                    is_favorite=bool(row['ZFAVORITE']),
                    is_hidden=bool(row['ZHIDDEN']),
                    album_names=[]
                ))
            return photos
        finally:
            conn.close()

    def get_favorites(self, limit: int = 25) -> List[PhotoInfo]:
        """Get favorited photos."""
        conn = self._connect()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT
                    ZUUID,
                    ZFILENAME,
                    ZORIGINALFILENAME,
                    ZDIRECTORY,
                    ZDATECREATED,
                    ZMODIFICATIONDATE,
                    ZWIDTH,
                    ZHEIGHT,
                    ZKIND,
                    ZFAVORITE,
                    ZHIDDEN
                FROM ZASSET
                WHERE ZTRASHEDSTATE = 0
                  AND ZKIND = 0
                  AND ZFAVORITE = 1
                ORDER BY ZDATECREATED DESC
                LIMIT ?
            ''', (limit,))

            photos = []
            for row in c.fetchall():
                file_path = self._resolve_photo_path(
                    row['ZUUID'],
                    row['ZDIRECTORY'],
                    row['ZFILENAME']
                )
                photos.append(PhotoInfo(
                    uuid=row['ZUUID'],
                    filename=row['ZFILENAME'] or '',
                    original_filename=row['ZORIGINALFILENAME'] or '',
                    directory=row['ZDIRECTORY'] or '',
                    file_path=file_path,
                    date_created=self._convert_timestamp(row['ZDATECREATED']),
                    date_modified=self._convert_timestamp(row['ZMODIFICATIONDATE']),
                    width=row['ZWIDTH'] or 0,
                    height=row['ZHEIGHT'] or 0,
                    file_size=0,
                    kind='image',
                    is_favorite=True,
                    is_hidden=bool(row['ZHIDDEN']),
                    album_names=[]
                ))
            return photos
        finally:
            conn.close()

    def search_by_filename(self, pattern: str, limit: int = 25) -> List[PhotoInfo]:
        """
        Search photos by filename pattern.

        Args:
            pattern: Filename pattern (SQL LIKE, use % for wildcard).
            limit: Maximum results.

        Returns:
            List of matching PhotoInfo objects.
        """
        conn = self._connect()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT
                    ZUUID,
                    ZFILENAME,
                    ZORIGINALFILENAME,
                    ZDIRECTORY,
                    ZDATECREATED,
                    ZMODIFICATIONDATE,
                    ZWIDTH,
                    ZHEIGHT,
                    ZKIND,
                    ZFAVORITE,
                    ZHIDDEN
                FROM ZASSET
                WHERE ZTRASHEDSTATE = 0
                  AND ZKIND = 0
                  AND (ZFILENAME LIKE ? OR ZORIGINALFILENAME LIKE ?)
                ORDER BY ZDATECREATED DESC
                LIMIT ?
            ''', (pattern, pattern, limit))

            photos = []
            for row in c.fetchall():
                file_path = self._resolve_photo_path(
                    row['ZUUID'],
                    row['ZDIRECTORY'],
                    row['ZFILENAME']
                )
                photos.append(PhotoInfo(
                    uuid=row['ZUUID'],
                    filename=row['ZFILENAME'] or '',
                    original_filename=row['ZORIGINALFILENAME'] or '',
                    directory=row['ZDIRECTORY'] or '',
                    file_path=file_path,
                    date_created=self._convert_timestamp(row['ZDATECREATED']),
                    date_modified=self._convert_timestamp(row['ZMODIFICATIONDATE']),
                    width=row['ZWIDTH'] or 0,
                    height=row['ZHEIGHT'] or 0,
                    file_size=0,
                    kind='image',
                    is_favorite=bool(row['ZFAVORITE']),
                    is_hidden=bool(row['ZHIDDEN']),
                    album_names=[]
                ))
            return photos
        finally:
            conn.close()

    def get_photo_by_uuid(self, uuid: str) -> Optional[PhotoInfo]:
        """Get single photo by UUID."""
        conn = self._connect()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT
                    ZUUID,
                    ZFILENAME,
                    ZORIGINALFILENAME,
                    ZDIRECTORY,
                    ZDATECREATED,
                    ZMODIFICATIONDATE,
                    ZWIDTH,
                    ZHEIGHT,
                    ZKIND,
                    ZFAVORITE,
                    ZHIDDEN
                FROM ZASSET
                WHERE ZUUID = ?
            ''', (uuid,))

            row = c.fetchone()
            if not row:
                return None

            file_path = self._resolve_photo_path(
                row['ZUUID'],
                row['ZDIRECTORY'],
                row['ZFILENAME']
            )
            return PhotoInfo(
                uuid=row['ZUUID'],
                filename=row['ZFILENAME'] or '',
                original_filename=row['ZORIGINALFILENAME'] or '',
                directory=row['ZDIRECTORY'] or '',
                file_path=file_path,
                date_created=self._convert_timestamp(row['ZDATECREATED']),
                date_modified=self._convert_timestamp(row['ZMODIFICATIONDATE']),
                width=row['ZWIDTH'] or 0,
                height=row['ZHEIGHT'] or 0,
                file_size=0,
                kind='image',
                is_favorite=bool(row['ZFAVORITE']),
                is_hidden=bool(row['ZHIDDEN']),
                album_names=[]
            )
        finally:
            conn.close()

    def copy_photo(self, uuid: str, destination: str) -> str:
        """
        Copy photo to destination.

        Args:
            uuid: Photo UUID.
            destination: Destination path.

        Returns:
            Path to copied file.

        Raises:
            FileNotFoundError: If photo not found.
        """
        photo = self.get_photo_by_uuid(uuid)
        if not photo:
            raise FileNotFoundError(f"Photo not found: {uuid}")

        if not photo.file_path or not os.path.exists(photo.file_path):
            raise FileNotFoundError(f"Photo file not accessible: {photo.file_path}")

        # Create destination directory if needed
        Path(destination).parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(photo.file_path, destination)
        return destination

    def _resolve_photo_path(self, uuid: str, directory: str, filename: str) -> str:
        """
        Resolve full path to photo file in Photos library.

        Photos stores originals in 'originals/' subdirectory organized by date folders.
        """
        if not directory or not filename:
            return ""

        # Try originals directory (modern structure)
        originals_path = Path(self.library_path) / "originals" / directory / filename
        if originals_path.exists():
            return str(originals_path)

        # Try Masters directory (older structure)
        masters_path = Path(self.library_path) / "Masters" / directory / filename
        if masters_path.exists():
            return str(masters_path)

        # Try resources directory
        resources_path = Path(self.library_path) / "resources" / "derivatives" / directory / filename
        if resources_path.exists():
            return str(resources_path)

        return ""

    def get_library_stats(self) -> dict:
        """Get library statistics."""
        conn = self._connect()
        try:
            c = conn.cursor()

            # Total photos
            c.execute('SELECT COUNT(*) FROM ZASSET WHERE ZTRASHEDSTATE = 0 AND ZKIND = 0')
            total_photos = c.fetchone()[0]

            # Total videos
            c.execute('SELECT COUNT(*) FROM ZASSET WHERE ZTRASHEDSTATE = 0 AND ZKIND = 1')
            total_videos = c.fetchone()[0]

            # Favorites
            c.execute('SELECT COUNT(*) FROM ZASSET WHERE ZTRASHEDSTATE = 0 AND ZFAVORITE = 1')
            favorites = c.fetchone()[0]

            # Albums
            c.execute('SELECT COUNT(*) FROM ZGENERICALBUM WHERE ZTRASHEDSTATE = 0 AND ZTITLE IS NOT NULL')
            albums = c.fetchone()[0]

            return {
                'total_photos': total_photos,
                'total_videos': total_videos,
                'favorites': favorites,
                'albums': albums,
                'library_path': self.library_path
            }
        finally:
            conn.close()
