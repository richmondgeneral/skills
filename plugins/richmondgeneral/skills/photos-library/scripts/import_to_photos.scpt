-- import_to_photos.scpt — import files into Photos and add to an album under
-- the "Richmond General" folder. Usage:
--   osascript import_to_photos.scpt "<Album Name>" <file1> [<file2> ...]
-- Prints: imported:<n>,album:<name>
on run argv
    if (count of argv) < 2 then error "usage: import_to_photos.scpt <album> <file...>"
    set albumName to item 1 of argv
    set filePaths to items 2 thru -1 of argv
    set rootName to "Richmond General"
    set posixFiles to {}
    repeat with p in filePaths
        set end of posixFiles to (POSIX file (contents of p))
    end repeat
    tell application "Photos"
        if not (exists folder named rootName) then make new folder named rootName
        set rootFolder to item 1 of (every folder whose name is rootName)
        if not (exists album named albumName of rootFolder) then
            make new album named albumName at rootFolder
        end if
        set targetAlbum to item 1 of (every album of rootFolder whose name is albumName)
        import posixFiles into targetAlbum skip check duplicates false
        return "imported:" & (count of posixFiles) & ",album:" & albumName
    end tell
end run
