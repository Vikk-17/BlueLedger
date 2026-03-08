use sqlx::{Postgres, Pool};

pub struct AppState {
    pub db: Pool<Postgres>,
}
