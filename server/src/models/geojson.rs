use serde::{Serialize, Deserialize};

type Point = Vec<f64>;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolygonGeoJson {
    #[serde(rename="type")]
    pub geometry_type: String,
    pub coordinates: Vec<Vec<Point>>,
}
