use actix_web::{get, post, web, HttpResponse, Responder, Result};
use crate::models::geojson::*;

#[get("/")]
pub async fn hello() -> impl Responder {
    HttpResponse::Ok().body("Hello world")
}

#[post("/geojson")]
pub async fn geo(geojson: web::Data<PolygonGeoJson>) -> Result<String> {
    Ok(format!("Testing: {}", geojson.geometry_type))
}
