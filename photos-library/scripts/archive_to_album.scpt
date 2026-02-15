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
        if not (exists folder rootFolderName) then
            make new folder named rootFolderName
        end if
        set rootFolder to folder rootFolderName

        -- 2. Ensure item album exists inside root folder
        if not (exists album itemId of rootFolder) then
            make new album named itemId at rootFolder
        end if
        set targetAlbum to album itemId of rootFolder

        -- 3. Collect media items by UUID
        set itemsToArchive to {}
        set skippedCount to 0
        repeat with pId in photoIds
            try
                set end of itemsToArchive to (first media item whose id is pId)
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
