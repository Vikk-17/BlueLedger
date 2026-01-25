import { Schema, model, connect, Types } from 'mongoose';

export interface IUser {
    username: string;
    email: string;
    password: string;
    // role: "admin" | "user";
    _id?: Types.ObjectId;
    createdAt?: Date;
    updatedAt?: Date;
}

export interface Image {
    imageKey: string;
    originalName: string;
    mimetype: string;
    size: number;
}

export interface Location {
    type: "Point" | "LineString" | "Polygon";
    coordinates: number[] | number[][] | number[][][]
}

export interface IPost {
    title: string;
    description: string;

    // S3 Data
    images: Array<Image>;

    // GeoJson format data 
    locations: Array<Location>;

    // user reference
    user: Types.ObjectId; // Id for the user document

    // System Time
    createdAt?: Date;
    updatedAt?: Date;
}

const UserSchema = new Schema<IUser>({
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
        // add regex for basic validation
        // match: [regexp, "Enter valid email address"]
    },
    password: {
        type: String,
        required: true,
        minlength: 6
    },

    // role: {
    //     type: String,
    //     enum: ["user", "admin"],
    //     default: "user"
    // }
});

const PostSchema = new Schema<IPost>({
    title: {
        type: String,
        required: true,
    },
    description: {
        type: String,
        required: true,
    },
    images: [{
        imageKey: {
            type: String,
            required: true,
        },
        originalName: String,
        mimetype: String,
        size: Number,
    }],

    location: {
        _id: false,
        type: {
            type: String,
            enum: ["Point", "LineString", "Polygon"],
            required: true
        },
        coordinates: {
            type: Schema.Types.Mixed,
            required: true
        }
    },

    // Link to the user collection
    // Add on feature while authentication
    user: {
        type: Schema.Types.ObjectId,
        ref: "User",
        required: true,
        index: true,
    }
});

// Index the 'locations' array for geospatial queries
PostSchema.index({ "locations": "2dsphere" });
const User = model<IUser>("User", UserSchema);
const Post = model<IPost>("Post", PostSchema);

export { User, Post };
