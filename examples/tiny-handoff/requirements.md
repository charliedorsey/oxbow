# Requirements

The demo tool reads UTF-8 text where each nonblank line contains three fields:

`title | owner | status`

It returns one JSON object per line with keys `title`, `owner`, and `status`.

Whitespace around fields is removed. Input order is preserved. Unknown status strings are preserved exactly after trimming.
