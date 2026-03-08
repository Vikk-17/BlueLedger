use uuid::Uuid;
use crate::state::state::AppState;
use bcrypt::{
    hash,
    DEFAULT_COST,
};
use actix_web::{get, post, web, HttpResponse, Responder};
use serde_json::json;
use crate::models::{
    geojson::*,
    users::User,
};

#[get("/")]
pub async fn hello() -> impl Responder {
    HttpResponse::Ok().body("Hello world")
}

#[post("/signup")]
pub async fn signup(state: web::Data<AppState>, user: web::Json<User>) -> impl Responder {
    let user = user.into_inner();
    // hash the password
    let id = Uuid::new_v4();
    let hashed_password = match hash(user.password, DEFAULT_COST) {
        Ok(value) => value,
        Err(_) => {
            return HttpResponse::InternalServerError().json(json!({
                "message": "Password hashing failed"
            }))
        }
    };

    let inserted_row = sqlx::query(
        r#"
        INSERT INTO users (id, firstname, lastname, email, password)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        "#,
    )
    .bind(id)
    .bind(user.firstname)
    .bind(user.lastname)
    .bind(user.email)
    .bind(hashed_password)
    .fetch_one(&state.db)
    .await;

    match inserted_row {
        Ok(_) => HttpResponse::Ok().json(json!({
        "message": "Successfully created user",
        "id": id,
        })),
        Err(_) => HttpResponse::InternalServerError().json(json!({
            "message": "User creation failed",
        }))
    }
}

// #[post("/login")]
// pub async fn signup() -> impl Responder {
//
// }

#[post("/geojson")]
pub async fn geo(geojson: web::Json<PolygonGeoJson>) -> impl Responder {
    let geojson = geojson.into_inner();
    HttpResponse::Ok().json(json!({
        "Name": geojson.name,
        "Geometry": geojson.geometry,
    }))
}
