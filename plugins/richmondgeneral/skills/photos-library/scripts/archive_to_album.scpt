-- archive_to_album.scpt
-- Moves processed product photos into a per-item album inside
-- "Richmond General Archive" folder in Photos.app.
--
-- Usage: osascript archive_to_album.scpt <ITEM_ID> <UUID_1> [UUID_2] ...
-- Example: osascript archive_to_album.scpt RG-0015 ABC123 DEF456 GHI789

on run argv
    if (count of argv) < 2 then
        error "Usage: osascript archive_to_album.scpt <ITEM_ID> <UUID_1> [UUID_2 ...]"
    end if

    set itemId to item 1 of argv
    set photoIds to items 2 thru -1 of argv

    set rootFolderName to "Richmond General Archive"

    tell application "Photos"
        -- 1. Ensure root folder exists
        if not (exists folder named rootFolderName) then
            make new folder named rootFolderName
        end if
        set matchingFolders to (every folder whose name is rootFolderName)
        if (count of matchingFolders) is 0 then
            error "Unable to create or locate Photos folder '" & rootFolderName & "'. Ensure Photos scripting has library read-write access."
        end if
        set rootFolder to item 1 of matchingFolders

        -- 2. Ensure item album exists inside root folder
        if not (exists album named itemId of rootFolder) then
            make new album named itemId at rootFolder
        end if
        set matchingAlbums to (every album of rootFolder whose name is itemId)
        if (count of matchingAlbums) is 0 then
            error "Unable to create or locate album '" & itemId & "' in Photos folder '" & rootFolderName & "'."
        end if
        set targetAlbum to item 1 of matchingAlbums

        -- 3. Collect media items by UUID
        set itemsToArchive to {}
        set skippedCount to 0
        repeat with pId in photoIds
            try
                -- Photos media item IDs include a suffix (e.g., "/L0/001").
                -- Upstream UUIDs from Photos.sqlite are bare ZUUID values.
                -- Direct id lookup first (instant); `whose id starts with` is a
                -- whole-library scan per photo (~1.1s each) — fallback only.
                try
                    set end of itemsToArchive to (media item id ((contents of pId) & "/L0/001"))
                on error
                    set end of itemsToArchive to (first media item whose id starts with (contents of pId))
                end try
            on error
                -- UUID not found (deleted or invalid), skip
                set skippedCount to skippedCount + 1
            end try
        end repeat

        -- 4. Add to item album
        set movedCount to count of itemsToArchive
        if movedCount > 0 then
            add itemsToArchive to targetAlbum
        end if

        -- 5. Return result as parseable string
        return "archived:" & movedCount & ",skipped:" & skippedCount & ",album:" & itemId
    end tell
end run
