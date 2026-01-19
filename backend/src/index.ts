import express from "express";
import { Schema, model, connect } from 'mongoose';
import dotenv from 'dotenv'
// import * as Minio from 'minio'
import { User } from "./db";
import multer from "multer";
import path from "path";
import { fileURLToPath } from "url";

const upload = multer({ dest: 'uploads/' })
// const __filename = fileURLToPath(import.meta.url);
const dirname = path.dirname(__filename);

dotenv.config({ path: './.env' })
// const minioClient = new Minio.Client({
//   endPoint: 'play.min.io',
//   port: 9000,
//   useSSL: true,
//   accessKey: 'test',
//   secretKey: 'test123',
// })

// set up multer storage
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, '/uploads')
  },
  filename: function (req, file, cb) {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9)
    cb(null, file.fieldname + '-' + uniqueSuffix)
  }
});

const app = express();
const PORT = 8000;
let DB_URL: string | undefined = process.env.DATABASE_URL;

// -- Middleware --
app.use(express.json())

if (DB_URL == undefined) {
    DB_URL = "http://localhost:27017/testDB";
}

async function connectDB(conn_string: string) {
    // 3. Connect to MongoDB
    await connect(conn_string)
}

try {
    connectDB(DB_URL);
    console.log("Database connection is successful")
} catch(err) {
    console.log(err)
}

// app.get("/", (req, res) => {
//     res.json({
//         "message": "Testing"
//     });
// });

app.post("/test", async (req, res) => {
    const username = req.body.username;
    const password = req.body.password;

    const user = new User({
        username,
        password
    });
    try {
        const response = await user.save();
        res.json({
            "message": "Saved successful",
            "id": response._id,
        })
    } catch(err) {
        console.log("Submission did not happen");
    }
});

app.get("/", (req, res) => {
  res.send(`
    <h1>File Upload Demo</h1>
    <form action="/upload/images" method="post" enctype="multipart/form-data">
        <input type="file" name="uploadedFile" />
        <button type="submit">Upload</button>
    </form>
  `);
});

app.post("/upload/images", upload.single('uploadedFile'), (req, res) => {
  console.log(req.file); // Contains file info
  if (req.file != undefined) {
      res.send(`File uploaded successfully: ${req.file.filename}`);
  }
  else {
      res.send("Error while uploading images")
  }
});

// app.post('/upload', upload.single("file"), (req, res) => {
//
// });

app.listen(PORT, () => {
    console.log(`Server is listening on http://localhost:${PORT}`);
})
