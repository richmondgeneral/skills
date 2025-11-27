# Contacts Reference

## Favorite Contacts

### Freeman Beilfuss (Dad)
- **Phone**: +12242308079
- **Service**: RCS (Android)
- **AppleScript ID**: `E91298EB-BC75-4C35-9F62-8FADC3564235`
- **Style**: Military/radio vibe — "10-4", "copy that", "over and out", "WILCO"
- **Emojis**: 🇺🇸 🦅 🫡 👍 💥
- **"The usual"**: 1.5L Cabernet Sauvignon (~$7.99 at Benny's — Liberty Creek or Woodbridge)

### Dawn Zurick
- **Phone**: +18472871148
- **Aliases**: Don (autocorrect)
- **Service**: iMessage
- **AppleScript ID**: `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4`
- **Relationship**: Majority owner, Richmond General
- **Style**: Casual, friendly. Often "That's cute" to funny images. Texts about household, school, errands.

### Jennifer Long
- **Phone**: +16305444884
- **Service**: iMessage
- **AppleScript ID**: `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4`
- **Relationship**: Business partner (Richmond General finances)
- **Style**: Professional, detail-oriented. Handles accounting/reimbursements.

### Mike (Richmond/Flea Market)
- **Phone**: +13129143889
- **Service**: RCS
- **AppleScript ID**: `E91298EB-BC75-4C35-9F62-8FADC3564235`
- **Context**: Richmond General store operations, flea market, food truck discussions
- **Note**: There are multiple "Mike" contacts — always verify by checking last message date

### Jeff Thompson
- **Phone**: +18475677182
- **Service**: iMessage
- **AppleScript ID**: `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4`
- **Context**: Store visits, check-ins ("At store. Call u later")

### Amy D (HOA)
- **Phone**: +17736763930
- **Service**: iMessage
- **AppleScript ID**: `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4`
- **Context**: HOA matters, drywall repairs, dues, Shagbark neighborhood

---

## Group Chats

| Name | Chat ID | Participants | Purpose |
|------|---------|--------------|---------|
| Dawn & Jennifer | 980 | Dawn, Jennifer | Business/financial discussions, Square, checks |
| HOA Drywall Group | 1343 | Dawn, Amy, neighbors | Drywall repairs, HOA coordination |
| Shagbark Neighbors | 1053 | Dawn, Amy, multiple neighbors | Neighborhood coordination |

**To find new group chats:**
```bash
python3 get_imessage_convo.py --groups
```

---

## Service ID Reference

| Service | AppleScript ID |
|---------|----------------|
| iMessage | `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4` |
| SMS | `E0595A22-53AF-4ECC-93BE-D717796D445F` |
| RCS | `E91298EB-BC75-4C35-9F62-8FADC3564235` |

**For unknown contacts:** Query last successful send from chat.db before sending.
