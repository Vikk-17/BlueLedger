import { Schema, model, Types } from "mongoose";

export interface IUser {
    _id?: Types.ObjectId;
    username: string;
    email: string;
    password: string;
    createdAt?: Date;
    updatedAt?: Date;
}

const UserSchema = new Schema<IUser>(
    {
        username: {
            type: String,
            required: true,
            trim: true,
            minlength: 3,
        },
        email: {
            type: String,
            required: true,
            unique: true,
            lowercase: true,
            trim: true,
        },
        password: {
            type: String,
            required: true,
            minlength: 6,
            select: false,
        },
    },
    {
        timestamps: true,
    }
);

export interface Image {
    imageKey: string;
    originalName?: string;
    mimetype?: string;
    size?: number;
}

export type GeoJSONType = "Point" | "LineString" | "Polygon";

export interface Location {
    type: GeoJSONType;
    coordinates: number[] | number[][] | number[][][];
}

export interface IPost {
    _id?: Types.ObjectId;
    title: string;
    description: string;
    images: Image[];
    locations: Location[];
    user: Types.ObjectId;
    createdAt?: Date;
    updatedAt?: Date;
}

const PostSchema = new Schema<IPost>(
    {
        title: {
            type: String,
            required: true,
            trim: true,
        },
        description: {
            type: String,
            required: true,
            trim: true,
        },

        images: [
            {
                imageKey: {
                    type: String,
                    required: true,
                },
                originalName: String,
                mimetype: String,
                size: Number,
            },
        ],

        locations: [
            {
                _id: false,
                type: {
                    type: String,
                    enum: ["Point", "LineString", "Polygon"],
                    required: true,
                },
                coordinates: {
                    type: Schema.Types.Mixed,
                    required: true,
                },
            },
        ],

        user: {
            type: Schema.Types.ObjectId,
            ref: "User",
            required: true,
            index: true,
        },
    },
    {
        timestamps: true,
    }
);


// GeoSpatial index for GeoJSON queries
PostSchema.index({ locations: "2dsphere" });


const User = model<IUser>("User", UserSchema);
const Post = model<IPost>("Post", PostSchema);

export { User, Post };
