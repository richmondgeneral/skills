# Plugin source of truth moved

**Claude plugin SoT:** monorepo  
`richmondgeneral/workspace` → `packages/richmondgeneral-plugin` (`@rg/richmondgeneral-plugin`)

Develop and test skills in the monorepo. This `skills` repository remains a
**compatibility / marketplace publish mirror** until CI re-exports from monorepo.

```bash
cd path/to/richmondgeneral/workspace
pnpm --filter @rg/richmondgeneral-plugin test
```

Seller-agent: `apps/seller-agent` (not `ops/seller-agent`).
