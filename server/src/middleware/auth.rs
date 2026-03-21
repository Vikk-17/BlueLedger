use futures::future::{LocalBoxFuture, Ready, ok};
use actix_web::{
    HttpMessage,
    Error, 
    HttpResponse,
    dev::{forward_ready, Service, ServiceRequest, ServiceResponse, Transform}
};
use std::{future::Future, pin::Pin};
use jsonwebtoken::{decode, DecodingKey, Validation};
pub struct JwtMiddleware {
    secret: String,
}
use serde_json::json;

impl JwtMiddleware {
    pub fn new(secret: impl Into<String>) -> Self {
        Self { secret: secret.into() }
    }
}

impl<S, B> Transform<S, ServiceRequest> for JwtMiddleware
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error>,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type InitError = ();
    type Transform = JwtMiddlewareService<S>;
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ok(JwtMiddlewareService {
            service,
            secret: self.secret.clone(),
        })
    }
}

pub struct JwtMiddlewareService<S> {
    service: S,
    secret: String,
}

impl<S, B> Service<ServiceRequest> for JwtMiddlewareService<S>
where 
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error>,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error    = Error;
    // type Future   = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>>>>;

    type Future = LocalBoxFuture<'static, Result<Self::Response, Self::Error>>;

    forward_ready!(service);

    fn call(&self, req: ServiceRequest) -> Self::Future {

        let auth_header = req
            .headers()
            .get("Authorization")
            .and_then(|v| v.to_str().ok())
            .map(|s| s.to_owned()); // clone before req is moved

        // secret is also clone before req is moved
        let secret = self.secret.clone();

        // verify and decode
        // let claims_result = verify_token(auth_header, &secret);
        // match claims_result {
        //     Ok(claims) => {
        //         req.extensions().insert(claims);
        //         let fut  = self.service.call(req);
        //         Box::pin(async move { fut.await })
        //     }
        //     Err(msg) => {
        //         Box::pin(async move {
        //             Ok(req.into_response(
        //                     HttpResponse::Unauthorized()
        //                     .json(json!({
        //                         "error": msg
        //                     }))
        //                     .map_into_right_body()
        //             ))
        //         })
            // }
        // }
}
