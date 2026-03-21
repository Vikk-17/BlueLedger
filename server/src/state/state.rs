use sqlx::{Postgres, Pool};
use crate::config::Config;

pub struct AppState {
    pub db: Pool<Postgres>,
    pub config: Config,
}
