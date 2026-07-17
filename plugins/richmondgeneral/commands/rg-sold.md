---
description: Mark a Richmond General item SOLD across all surfaces (page, gallery, Square) and kill the payment link
argument-hint: "[RG-XXXX] [sold price / channel]"
---

Use the **rg-item-mark-sold** skill to take an item down cleanly across every surface: migrate the GitHub item card and the gallery grid card to the sold-archive pattern (brown SOLD badge, "Sold · $X", sold-status panel), write `status.json` with the sold metadata, and **delete the Square payment link** via API so the printed QR / bookmarked checkout URL can no longer charge a phantom sale. Then validate and commit/push.

Item: $ARGUMENTS

Invoke `rg-item-mark-sold` now. (Use this only for a genuine purchase of a unique item — for loss/giveaway/damage use the inventory-loss path instead.)
