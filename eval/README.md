# FashionCLIP fixture eval

Not part of `just test` or CI. Those never load FashionCLIP. This harness scores a
small labeled JSONL against the live model so prompt and ranking changes can be
measured (hit@1, winner `gap`, exclusive-pool `p`).

```bash
just eval
just eval --baseline generic --out eval/out/report.json
```

`--baseline generic` re-scores the same fixtures with the old shared caption
`a garment with {label}` and prints accuracy delta versus aspect-specific
captions.

## Fixture schema

One JSON object per line:

```json
{
  "id": "shadow-black-leggings",
  "image_url": "https://example.com/garment.jpg",
  "options": {
    "pattern": true,
    "product-type": true,
    "subjects": true
  },
  "expect": {
    "pattern": {"winner": "Plain"},
    "product-type": {"winner": "Leggings"},
    "subjects": {"winner": "Safari"}
  }
}
```

Set `"subjects": true` in `options` when judging graphic-theme hits.

`expect` is optional and partial. Add 30–80 labeled SKUs here when you have
them; keep this file out of the Lambda image.
