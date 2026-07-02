# Agent Chat V1 Validation Checklist

## Local Backend

- [ ] Health endpoint returns ok
- [ ] Select-targets works for event_id mode
- [ ] Select-targets works for source+window mode
- [ ] Verify returns score/level/verdict/evidence/unknowns/conflicts
- [ ] Propose-options returns 3 tiers

## Local Frontend

- [ ] Can trigger mixed-mode flow from UI
- [ ] Reliability panel renders score and verdict
- [ ] Options panel renders at least one option

## Security

- [ ] Verify endpoint rejects invalid internal key
- [ ] Runtime uses read-only DB credential

## Deployment

- [ ] Backend deployed to long-running service
- [ ] Frontend deployed to Vercel
- [ ] Vercel env vars configured correctly
