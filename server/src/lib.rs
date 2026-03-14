mod routes;
mod models;
mod state;
mod middleware;

use actix_web::{web, App, HttpServer};
use routes::handlers::*;
// use models::{
//     geojson::*,
//     users::*
// };
use dotenvy::dotenv;
use sqlx::{Pool, Postgres};
use sqlx::postgres::PgPoolOptions;
use crate::state::state::AppState;

pub async fn run() -> std::io::Result<()> {

    env_logger::init_from_env(env_logger::Env::default().default_filter_or("debug"));
    dotenv().ok();

    // DB pool creation
    let db_uri: String = std::env::var("DATABASE_URL")
        .expect("Invalid Database Url");

    let pool: Pool<Postgres> = match PgPoolOptions::new()
        .max_connections(3)
        .connect(&db_uri)
        .await
        {
            Ok(pool) => {
                println!("Database connection is successful");
                pool
            }
            Err(err) => {
                println!("Failed to connect to the database {:?}", err);
                std::process::exit(1);
            }
        };

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(AppState {
                db: pool.clone()
            }))
            .service(hello)
            .service(geo)
            .service(signup)
            .service(login)
    })
    .bind(("0.0.0.0", 8000))?
        .workers(3)
        .run()
        .await
}
