- For fetch_all need to use match first and then vector to interate through.
- Mapped TIMESTAMPZ of sql to rust, used chrono feature in the sqlx package
- Used serde feature in chrono to solve the serialization issue while fetching the time from db
- Null can be fetched directly | will panic otherwise | eg, resolved_at timing, so I use Option<> to make it fetchable.

## Reference
- [Writing middleware using actix](https://oneuptime.com/blog/post/2026-02-03-actix-middleware/view)
- [JsonWebToken](https://github.com/Keats/jsonwebtoken)
- [Iterators](https://hermanradtke.com/2015/06/22/effectively-using-iterators-in-rust.html/)
- [DateTime Fix](https://stackoverflow.com/questions/59760741/how-can-i-read-a-timestamp-with-timezone-timestamptz-value-from-postgresql-in#59761805)
