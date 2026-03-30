use crate::models::jwt::Claims;
use crate::models::{geojson::*, users::*};
use crate::state::state::AppState;
use actix_web::{
    HttpRequest, HttpResponse, HttpMessage, Responder, get, post,
    web::{Data, Json, Path},
};
use bcrypt::DEFAULT_COST;
use chrono::{Duration, Utc};
use jsonwebtoken::{EncodingKey, Header, encode};
use serde_json::json;
use sqlx::Row;
use uuid::Uuid;
use std::collections::HashMap;

#[get("/")]
pub async fn hello() -> impl Responder {
    HttpResponse::Ok().body("Hello world")
}

#[post("/signup")]
pub async fn signup(state: Data<AppState>, payload: Json<SignupUser>) -> impl Responder {
    let user = payload.into_inner();

    // Creating the payload
    let id = Uuid::new_v4();
    let fullname: String = format!("{} {}", user.firstname, user.lastname);
    let hashed_password = match bcrypt::hash(user.password, DEFAULT_COST) {
        Ok(value) => value,
        Err(_) => {
            return HttpResponse::InternalServerError().json(json!({
                "message": "Password hashing failed"
            }));
        }
    };

    let inserted_row = sqlx::query(
        r#"
        INSERT INTO users (id, fullname, username, password_hash)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        "#,
    )
    .bind(id)
    .bind(fullname)
    .bind(user.username)
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
        })),
    }
}

#[post("/login")]
pub async fn login(state: Data<AppState>, payload: Json<LoginUser>) -> impl Responder {
    let user = payload.into_inner();

    // check if the user exists
    let result = sqlx::query(
        r#"
        SELECT id, username, password_hash from users
        WHERE username=$1
        "#,
    )
    .bind(&user.username)
    .fetch_one(&state.db)
    .await;
    match result {
        Ok(row) => {
            // verify the user with password
            let hashed_password = row.get("password_hash");
            let is_valid: bool = bcrypt::verify(&user.password, hashed_password).unwrap_or(false);
            if is_valid {
                let secret = state.config.secret_key.clone();
                let claims = Claims {
                    sub: row.get("id"), // user id
                    exp: (Utc::now() + Duration::hours(24)).timestamp() as u64,
                    iat: Utc::now().timestamp() as u64,
                };

                // This will create a JWT using HS256 as algorithm
                let token = encode(
                    &Header::default(),
                    &claims,
                    &EncodingKey::from_secret(secret.as_ref()),
                )
                .unwrap();

                HttpResponse::Ok().json(json!({
                    "message": "Login Successful",
                    "token": token,
                }))
            } else {
                HttpResponse::Unauthorized().json(json!({
                    "message": "Invalid email or password"
                }))
            }
        }

        Err(_) => HttpResponse::NotFound().json(json!({
            "message": "User not found"
        })),
    }
}

#[post("/geojson")]
pub async fn geo(geojson: Json<PolygonGeoJson>) -> impl Responder {
    let geojson = geojson.into_inner();
    HttpResponse::Ok().json(json!({
        "Name": geojson.name,
        "Geometry": geojson.geometry,
    }))
}

#[post("/plots")]
pub async fn register_plots(
    req: HttpRequest,
    state: Data<AppState>,
    geojson: Json<PolygonGeoJson>,
) -> impl Responder {
    // access the injected token extension
    // req.extensions is temporary value coming from middleware
    // so the get method referencing the the empty value, will not work
    // let claims = req.extensions().get::<Claims>().unwrap();

    let extensions = req.extensions();
    let claims = extensions.get::<Claims>().unwrap();
    let sub = &claims.sub;
    let uuid = Uuid::new_v4();
    let geojson = geojson.into_inner();
    let location_name = geojson.name;
    let geojson_str = serde_json::to_string(&geojson.geometry).unwrap();

    let result = sqlx::query(
        r#"
        INSERT INTO plots (id, user_id, geom, location_name)
        VALUES ($1, $2, ST_GeomFromGeoJSON($3), $4)
        RETURNING id
        "#,
    )
    .bind(uuid) // uuid for plot generated in local scope
    .bind(sub) // user_id
    .bind(geojson_str)
    .bind(location_name)
    .fetch_one(&state.db)
    .await;

    match result {
        Ok(row) => {
            let uuid: Uuid = row.get("id");
            HttpResponse::Ok().json(json!({
                "message": "Plot registered",
                "ID": uuid,
            }))
        }
        Err(e) => HttpResponse::InternalServerError().json(json!({
            "error": e.to_string(),
            "message": "Failed to registered",
        })),
    }
}

#[get("/plots")]
pub async fn get_plots(req: HttpRequest, state: Data<AppState>) -> impl Responder {
    let extensions = req.extensions();
    let claims = extensions.get::<Claims>().unwrap();
    let sub: &Uuid = &claims.sub;

    let result = sqlx::query(
        r#"
        SELECT id, ST_AsGeoJSON(geom) as geom, area_sqm, location_name
        FROM plots
        WHERE user_id = $1
        "#,
    )
    .bind(&sub)
    .fetch_all(&state.db) // returns Result<Vec<Row>, sqlx::Error>
    .await;

    match result {
        Ok(rows) => {
            if rows.is_empty() {
                return HttpResponse::NotFound().json(json!({
                    "message": "No plot found", // Fix (CDD): might have return it with ;
                }));
            }

            let plots: Vec<_> = rows.into_iter().map(|row| {
                let id: Uuid = row.get("id");
                let location_name: String = row.get("location_name");
                let area: f64 = row.get("area_sqm");
                let geom_str: String = row.get("geom");
                let geom_json: serde_json::Value = serde_json::from_str(&geom_str).unwrap();

                json!({
                    "id": id,
                    "location_name": location_name,
                    "area": area,
                    "geometry": geom_json,
                })
            }).collect();

            HttpResponse::Ok().json(plots)
        }

        Err(e) => {
            HttpResponse::InternalServerError().json(json!({
                "message": "Internal Server Error",
                "error": e.to_string(),
            }))
        }
    }
}

#[get("/plots/{id}")]
pub async fn get_plots_with_id(
    state: Data<AppState>,
    path: Path<(Uuid,)>
    ) -> impl Responder {

    let path = path.into_inner();
    let plot_id: Uuid = path.0;

    let result = sqlx::query(
        r#"
        SELECT id, ST_AsGeoJSON(geom) as geom, area_sqm, location_name
        FROM plots
        WHERE id = $1
        "#,
    )
    .bind(plot_id)
    .fetch_one(&state.db) // returns Result<Row, sqlx::Error>
    .await;

    match result {
        Ok(row) => {
            let id: Uuid = row.get("id");
            let location_name: String = row.get("location_name");
            let area: f64 = row.get("area_sqm");
            let geom_str: String = row.get("geom");
            let geom_json: serde_json::Value = serde_json::from_str(&geom_str).unwrap();

            HttpResponse::Ok().json(json!({
                    "id": id,
                    "location_name": location_name,
                    "area": area,
                    "geometry": geom_json,
            }))
        }

        Err(e) => {
            HttpResponse::NotFound().json(json!({
                "message": "No Plot Found",
                "error": e.to_string(),
            }))
        }
    }
}

// testing for integration
#[get("/ping")]
pub async fn check_health() -> impl Responder {
    let response = reqwest::get("http://localhost:8000/health")
        .await
        .unwrap()
        .text()
        .await
        .unwrap();

    println!("{:#?}", response);

    HttpResponse::Ok().json(json!({
        "messge": "Pong",
    }))
}

#[post("/analyze")]
pub async fn analyze() -> impl Responder {
    let json_data = json!({
        "UUID": "asdfaf-afasfasf",
        "name": "Delivery Zone A",
        "type": "Polygon",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [81.15, 19.48],
                    [81.15, 19.45],
                    [81.20, 19.45],
                    [81.20, 19.48],
                    [81.15, 19.48]
                ]
            ]
        }
    });
    let client = reqwest::Client::new();

    let response = client.post("http://localhost:8000/run")
        .json(&json_data)
        .send()
        .await
        .unwrap()
        .text()
        .await
        .unwrap();

    let parsed: serde_json::Value = serde_json::from_str(&response).unwrap();
    println!("{:#}", parsed);

    HttpResponse::Ok().json(json!({
        "messge": "working",
    }))
}
