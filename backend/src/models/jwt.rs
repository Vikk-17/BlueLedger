use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    // pub username: String,
    // This will be coming from the database (pushed by rust backend uuid)
    pub sub: Uuid, // uuid (user_id)
    pub exp: u64,
    pub iat: u64,
}
