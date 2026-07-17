# Renvooiservice — contract-schets (fase 5)

Dunne HTTP-laag (FastAPI) over `storm.renvooi`. Komt pas nadat de
diff-functies als CLI werken (fase 2–4); zie ARCHITECTUUR.md §6b.

Beoogd contract (concept):

```
POST /diff            twee STORM-pakketten (of verwijzingen) -> diffmodel
GET  /diff/{id}/stop-renvooi   tekst-as als HTML-renvooi
GET  /diff/{id}/ow-diff        object-as als rapport
GET  /diff/{id}/gio-renvooi    geo-as als rapport
POST /samenloop       n pakketten op één regeling -> conflictrapport
```
