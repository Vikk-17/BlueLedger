mod routes;
mod models;
mod state;
mod config;
// mod middleware;

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
use crate::config::*;

pub async fn run() -> std::io::Result<()> {

    env_logger::init_from_env(env_logger::Env::default().default_filter_or("debug"));
    dotenv().ok();

    // load the config via envs
    let config: Config = envy::from_env().unwrap();

    let db_uri: String = config.database_url;
    let jwt_secret: String = config.secret_key;


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
    .bind(("0.0.0.0", 9000))?
        .workers(3)
        .run()
        .await
}
