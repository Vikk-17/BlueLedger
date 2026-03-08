use serde::{Serialize, Deserialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct User {
    pub firstname: String,
    pub lastname: String,
    pub email: String,
    pub password: String,
}
