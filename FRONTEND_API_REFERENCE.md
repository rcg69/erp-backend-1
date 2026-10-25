# Student ERP Frontend API Reference

Backend base URL during local development:

```text
http://127.0.0.1:8000
```

The API is served by `server.py`. Unless an endpoint is marked **Public**, send the login token in this header:

```http
Authorization: Bearer <access_token>
```

## Endpoint Summary

| Method | Endpoint | Access | Frontend use |
| --- | --- | --- | --- |
| GET | `/health` | Public | Check whether the API is running |
| POST | `/api/auth/login` | Public | Sign in and receive an access token |
| POST | `/api/auth/refresh` | Refresh cookie | Rotate the refresh token and receive a new access token |
| POST | `/api/auth/logout` | Refresh cookie | Revoke the refresh token and clear the cookie |
| GET | `/api/auth/me` | Authenticated | Load the current signed-in user |
| GET | `/api/user-details/me` | Authenticated | Load the signed-in user's personal profile |
| PATCH | `/api/user-details/me` | Authenticated | Update the signed-in user's profile |
| GET | `/api/user-details/{user_id}` | Admin; staff assigned to a student | Load a user's profile |
| PATCH | `/api/user-details/{user_id}` | Admin; staff assigned to a student | Update a user's profile |
| PUT | `/api/user-images/users/{user_id}` | Admin; staff updating their own image; assigned teacher updating a student in their assigned class | Upload or replace a profile image |
| GET | `/api/user-images/{image_id}` | Authenticated | Load an image by its ID |
| POST | `/api/exams` | Admin only | Create an exam for an existing class/year |
| GET | `/api/exams` | Admin only | List/filter exams |
| GET | `/api/exams/{exam_id}` | Admin only | Retrieve an exam |
| PUT | `/api/exams/{exam_id}` | Admin only | Edit a draft exam |
| DELETE | `/api/exams/{exam_id}` | Admin only | Delete a draft exam with no marks |
| POST | `/api/exams/{exam_id}/roster/sync` | Admin only | Add newly active students to a draft exam roster |
| POST | `/api/exams/{exam_id}/subjects` | Admin only | Configure a subject and evaluator |
| GET | `/api/exams/{exam_id}/subjects` | Admin only | List configured subjects and progress |
| PUT | `/api/exams/{exam_id}/subjects/{exam_subject_id}` | Admin only | Edit subject settings or evaluator |
| DELETE | `/api/exams/{exam_id}/subjects/{exam_subject_id}` | Admin only | Remove a subject from a draft exam |
| POST | `/api/exams/{exam_id}/schedule` | Admin only | Schedule a configured exam |
| POST | `/api/exams/{exam_id}/publish` | Admin only | Publish completed results |
| POST | `/api/exams/{exam_id}/publish-override` | Admin only | Publish entered marks for a scheduled exam before its normal completion |
| GET | `/api/exams/{exam_id}/progress` | Admin only | Review subject evaluation progress |
| GET | `/api/exams/assigned` | Assigned staff only | List the evaluator's assigned subjects |
| GET | `/api/exams/assigned/subjects/{exam_subject_id}/roster?limit={limit}&offset={offset}` | Assigned staff only | Load a page of roster and marks |
| PUT | `/api/exams/assigned/subjects/{exam_subject_id}/marks/{student_id}` | Assigned staff only | Enter/update marks while evaluation is open |
| POST | `/api/exams/assigned/subjects/{exam_subject_id}/complete` | Assigned staff only | Complete and lock subject evaluation |
| GET | `/api/exams/student?limit={limit}&offset={offset}` | Enrolled student | List the requesting student's scheduled, completed, and published exams |
| GET | `/api/exams/student/{exam_id}/subjects` | Enrolled student | View subject mark allocations for an exam in the student's roster |
| GET | `/api/exams/results/{exam_id}?limit={limit}&offset={offset}` | Admin; assigned staff; enrolled student | Review results or read published results |
| PUT | `/api/exams/exam-subjects/{exam_subject_id}/marks/{student_id}/correction` | Admin only | Correct marks with a required audit reason |
| GET | `/api/attendance?academic_year={academic_year}` | Authenticated | List attendance, optionally filtered by academic year |
| GET | `/api/attendance/student-report?roll_number={roll_number}&academic_year={academic_year}` | Public | Get a student's attendance for the selected academic year |
| GET | `/api/attendance/teacher/classes` | Staff only | Get the signed-in teacher's assigned classes for a date |
| GET | `/api/attendance/teacher/sessions/{session_id}/roster` | Staff only | Load the class roster and existing attendance |
| PUT | `/api/attendance/teacher/sessions/{session_id}/attendance` | Assigned staff only | Save or update attendance for that class session |
| GET | `/api/classes/students?grade={grade}&section={section}&academic_year={academic_year}` | Admin; staff assigned to that class | Load active students for one class |
| GET | `/api/students` | Authenticated | List all students |
| GET | `/api/students/{student_id}` | Authenticated | View one student |
| POST | `/api/students` | Admin only | Create a student |
| PUT | `/api/students/{student_id}` | Admin only | Update a student |
| DELETE | `/api/students/{student_id}` | Admin only | Delete a student |
| GET | `/api/users` | Authenticated | List all users |
| GET | `/api/users/{user_id}` | Authenticated | View one user |
| POST | `/api/users` | Authenticated | Create a user |
| PUT | `/api/users/{user_id}` | Authenticated | Update a user |
| DELETE | `/api/users/{user_id}` | Authenticated | Delete a user |
| GET | `/api/roles` | Authenticated | List available roles |

## Authentication

### `GET /health`

Public health check.

Response:

```json
{
  "status": "ok",
  "message": "API is running"
}
```

### `POST /api/auth/login`

Public login endpoint.

Request body:

```json
{
  "email": "admin@gmail.com",
  "password": "ram123"
}
```

The email must be valid and the password must contain 1 to 128 characters.

Successful response:

```json
{
  "success": true,
  "message": "Login successful",
  "access_token": "<jwt-token>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "person_id": null,
    "role_id": 1,
    "is_active": true
  }
}
```

Store `access_token` in the frontend and send it as a Bearer token for protected requests. A failed login returns `401` with an error detail.

The backend also sets an HttpOnly `refresh_token` cookie. The frontend must include credentials on login and all auth requests:

```js
fetch(`${API_BASE_URL}/api/auth/login`, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password }),
});
```

Access tokens expire after 15 minutes by default. Refresh cookies expire after 7 days by default. The refresh token is not returned in the JSON response or exposed to JavaScript.

### `POST /api/auth/refresh`

Reads the HttpOnly refresh cookie, verifies its signature, type, expiration, database record, and active user status. The old refresh token is revoked and a new refresh cookie is issued.

Request body: none. Send `credentials: "include"`.

Response:

```json
{
  "access_token": "new-access-token",
  "token_type": "bearer",
  "expires_in": 900
}
```

### `POST /api/auth/logout`

Revokes the current refresh token and clears the HttpOnly cookie. Send `credentials: "include"`.

Response:

```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

### `GET /api/auth/me`

Returns the currently authenticated user. Requires a valid, active-user token.

Response:

```json
{
  "id": 1,
  "email": "admin@gmail.com",
  "username": "admin",
  "person_id": null,
  "role_id": 1,
  "is_active": true
}
```

## User Details

A profile row is created automatically with each account, and existing accounts receive a blank profile during database startup migration. Profile fields can be completed and edited after login without changing the user's login credentials or role.

### `GET /api/user-details/me`

Returns the signed-in user's profile. All fields start as `null` except `same_as_present_address`, which starts as `false`. Requires authentication.

### `PATCH /api/user-details/me`

Updates only the supplied fields; omitted fields remain unchanged. Every personal, contact, family/guardian, and present/permanent address field can be supplied. For example:

```json
{
  "full_name": "Rahul Kumar",
  "gender": "Male",
  "date_of_birth": "2008-03-12",
  "nationality": "Indian",
  "mobile_number": "9876543210",
  "present_house_flat_number": "12-A",
  "present_street_locality": "Main Road",
  "present_village_town_city": "Hyderabad",
  "present_district": "Hyderabad",
  "present_state": "Telangana",
  "present_pin_code": "500001",
  "present_country": "India",
  "same_as_present_address": true
}
```

When `same_as_present_address` is `true`, the permanent address is copied from the present address and stays synchronized when present-address fields are updated. Set it to `false` to edit permanent-address fields independently. Aadhaar is optional; collect it only when required.
`image_id` is managed only through the profile-image API; do not include it in profile `PATCH` requests.

### Admin and assigned staff profile access

Administrators can use `GET /api/user-details/{user_id}` to fetch and `PATCH /api/user-details/{user_id}` to edit any user's profile. Staff/teachers can use these endpoints only for a student whose grade and section are assigned to their active staff profile. The server checks the current assignment on each request; staff cannot access other student profiles or other staff profiles. The self-service endpoints always use the authenticated user's ID and do not accept a user ID from the request.

Profile responses include `image_id` (`null` when no image has been uploaded). The image bytes and metadata are stored separately in `profile_images`; the profile keeps only the current image ID. Uploading a replacement creates a new image record, updates that ID, and deletes the user's previous image records in the same transaction. Image IDs are not reused. There is no image-delete endpoint.

### Profile images

`PUT /api/user-images/users/{user_id}` accepts a multipart form upload with a `file` field. Send the access-token `Authorization: Bearer <access-token>` header. JPEG, PNG, GIF, and WebP are supported, up to 5 MB.

Administrators can change any user's image. Staff/teachers can change their own image and a student's image only when that student's grade and section are assigned to them. Students cannot upload, replace, or delete profile images. Staff and administrators may change their own images.

Successful upload response:

```json
{
  "id": 42,
  "user_id": 17,
  "filename": "profile.png",
  "content_type": "image/png",
  "size_bytes": 24581,
  "created_at": "2026-10-21T12:00:00Z"
}
```

Use the returned `id` as `image_id` in profile state; the same ID is returned by `GET /api/user-details/me` or the authorized user's details endpoint. To display the image, request `GET /api/user-images/{image_id}` with the bearer token. Since an HTML `<img src>` cannot attach this header, fetch it with the authorization header, convert the response to a Blob, and use `URL.createObjectURL(blob)` as the image source. Revoke the object URL when it is no longer needed. After successful upload, refresh the user-details response so the frontend receives its current `image_id`.

Example upload (do not set `Content-Type` manually; the browser adds the multipart boundary):

```js
const formData = new FormData();
formData.append("file", selectedFile);

const response = await fetch(`${API_BASE_URL}/api/user-images/users/${userId}`, {
  method: "PUT",
  headers: { Authorization: `Bearer ${accessToken}` },
  body: formData,
});

if (!response.ok) {
  throw new Error((await response.json()).detail ?? "Image upload failed");
}

const uploadedImage = await response.json();
// Refresh user details; image_id is managed by the server.
```

An unauthorized role or unassigned class returns `403`; a missing user/image returns `404`; an invalid image returns `400`; a file larger than 5 MB returns `413`.

## Students

### `GET /api/classes/students`

Returns only active students in the requested active class. The `grade`, `section`, and `academic_year` query parameters are required. Administrators may request any active class; staff may request only a class assigned to their staff profile. This endpoint is intended for class rosters instead of fetching `/api/students` and filtering in the browser.

Example:

```http
GET /api/classes/students?grade=10&section=A&academic_year=2026-2027
Authorization: Bearer <access_token>
```

Response:

```json
{
  "academic_year": "2026-2027",
  "grade": "10",
  "section": "A",
  "count": 1,
  "students": [
    {
      "id": 42,
      "user_id": 71,
      "name": "Rahul Kumar",
      "roll_number": "23A91A0502",
      "admission_date": "2026-06-01",
      "parent_name": "Parent Name",
      "mobile_number": "9876543210",
      "grade": "10",
      "section": "A",
      "status": "active",
      "created_at": "2026-06-01T10:00:00Z"
    }
  ]
}
```

An inactive or nonexistent class returns `404`; staff requesting a class they are not assigned to receive `403`. The roster includes only students whose status is `active`.

The student request body is used by both create and update operations:

```json
{
  "name": "ram",
  "roll_number": "22211",
  "admission_date": "2026-09-23",
  "parent_name": "Parent Name",
  "mobile_number": "9876543210"
}
```

`name` and `roll_number` are required. `admission_date`, `parent_name`, and `mobile_number` are optional. `admission_date` must use `YYYY-MM-DD` format. In class-roster responses, `user_id` is the linked student login account ID when one exists; use it to open the student profile. The student record's `id` is not interchangeable with `user_id`.

### `GET /api/students`

Requires authentication. Returns every student.

Response:

```json
{
  "success": true,
  "count": 1,
  "students": [
    {
      "id": 1,
      "name": "Rahul Kumar",
      "roll_number": "23A91A0502",
      "admission_date": "2026-09-16",
      "parent_name": "Parent Name",
      "mobile_number": "9876543210",
      "status": "active",
      "created_at": "2026-09-16T10:00:00+00:00"
    }
  ]
}
```

### `GET /api/students/{student_id}`

Requires authentication. Replace `{student_id}` with the numeric student ID.

Response:

```json
{
  "success": true,
  "student": {
    "id": 1,
    "name": "Rahul Kumar",
    "roll_number": "23A91A0502",
    "admission_date": "2026-09-16",
    "parent_name": "Parent Name",
    "mobile_number": "9876543210",
    "status": "active",
    "created_at": "2026-09-16T10:00:00+00:00"
  }
}
```

### `POST /api/students`

Admin only. Returns `201 Created`.

Request body: use the student body shown above.

Successful response:

```json
{
  "success": true,
  "message": "Student created successfully",
  "student": { "id": 1, "name": "Rahul Kumar", "roll_number": "23A91A0502", "admission_date": "2026-09-16", "parent_name": "Parent Name", "mobile_number": "9876543210" }
}
```

### `PUT /api/students/{student_id}`

Admin only. Replace `{student_id}` with the numeric student ID. Returns the updated student in the same response shape as the create endpoint. The full student request body is required.

### `DELETE /api/students/{student_id}`

Admin only. Replace `{student_id}` with the numeric student ID.

Successful response:

```json
{
  "success": true,
  "message": "Student deleted successfully",
  "student": { "id": 1, "name": "Rahul Kumar", "roll_number": "23A91A0502", "admission_date": "2026-09-16", "parent_name": "Parent Name", "mobile_number": "9876543210" }
}
```

## Users

## Roles

### `GET /api/roles`

Requires authentication. Returns all roles ordered by `role_id`.

Response:

```json
[
  { "role_id": 1, "role_name": "admin" },
  { "role_id": 2, "role_name": "staff" },
  { "role_id": 3, "role_name": "student" },
  { "role_id": 4, "role_name": "parent" }
]
```

The request body for `POST /api/users` and `PUT /api/users/{user_id}` is:

```json
{
  "email": "student@example.com",
  "password": "password123",
  "username": "student_01",
  "role": "student",
  "person_id": 1
}
```

`person_id` is required when creating or updating a user. For a `student` account it must equal an existing student's `id`; for a `staff` account it must equal an existing staff member's `id`. The user's own `id` is generated separately; the linked student or staff ID is stored in `person_id`.

Validation rules:

- `email` must be a valid email address.
- `password` must contain 8 to 128 characters.
- `username` must contain 3 to 50 characters and only letters, numbers, `_`, `.`, or `-`.
- `role` is required and must match a role in the database, such as `admin` or `student`.
- `person_id` is required and numeric. It must reference a student for student accounts or staff member for staff accounts.

### `GET /api/users`

Requires authentication. Returns an array of users. Passwords are never returned.

Response:

```json
[
  {
    "id": 7,
    "email": "student@example.com",
    "username": "student_01",
    "person_id": 7,
    "role_id": 2,
    "is_active": true
  }
]
```

### `GET /api/users/{user_id}`

Requires authentication. Returns one user in the same object shape as the user list. A missing user returns `404`.

### `POST /api/users`

Requires authentication. Returns `201 Created` and the created user object. Passwords are not included in the response.

### `PUT /api/users/{user_id}`

Requires authentication. Replace `{user_id}` with the numeric user ID. Returns the updated user object.

The current backend schema marks `password` as required, so the frontend must send a password even when only changing the email, username, role, or person ID. The backend hashes the password before saving it.

### `DELETE /api/users/{user_id}`

Requires authentication. Returns:

```json
{
  "success": true,
  "message": "User deleted successfully",
  "user": {
    "id": 7,
    "email": "student@example.com",
    "username": "student_01",
    "person_id": 7,
    "role_id": 2,
    "is_active": true
  }
}
```

## Common Error Handling

FastAPI validation errors usually return `422` with a `detail` array. Other errors generally use this shape:

```json
{
  "detail": "Error message"
}
```

| Status | Meaning | Frontend behavior |
| --- | --- | --- |
| 401 | Missing, invalid, or expired token; invalid login | Clear the token and redirect to login when appropriate |
| 403 | Account inactive or admin access required | Show an authorization message |
| 404 | Requested user or student does not exist | Show a not-found state |
| 409 | Duplicate email or username | Show the field conflict to the user |
| 422 | Invalid request body or role | Display validation errors |
| 503 | Database or backend service unavailable | Show a retryable server error |

## Frontend Request Example

```js
const API_BASE_URL = "http://127.0.0.1:8000";
const token = localStorage.getItem("access_token");

const response = await fetch(`${API_BASE_URL}/api/students`, {
  headers: {
    Authorization: `Bearer ${token}`,
  },
  credentials: "include",
});

const data = await response.json();
```

For JSON `POST` and `PUT` requests, also send `Content-Type: application/json` and serialize the request body with `JSON.stringify(...)`.

When a protected request returns `401`, call `/api/auth/refresh` with `credentials: "include"`, replace the stored access token with the returned `access_token`, and retry the original request once. If refresh also returns `401`, clear the access token and redirect to login.

## Teacher attendance

Teacher attendance requests require a valid access token for a `staff` account. The account's `person_id` must be the ID of an active row in `staff`. When creating or updating a staff user, use the staff record's ID for `person_id`.

### `GET /api/attendance/teacher/classes`

Returns only class sessions assigned to the signed-in staff member. `session_date` is optional and uses `YYYY-MM-DD`; when omitted, the backend uses its current date. A dated session is created from the weekly timetable assignment when one does not exist yet.

Example:

```http
GET /api/attendance/teacher/classes?session_date=2026-10-12
Authorization: Bearer <access-token>
```

Response:

```json
{
  "session_date": "2026-10-12",
  "classes": [
    {
      "session_id": 42,
      "timetable_id": 8,
      "session_date": "2026-10-12",
      "grade_id": 3,
      "section_id": 1,
      "grade": "10",
      "section": "A",
      "subject_id": 5,
      "subject_name": "Mathematics",
      "period_number": 1,
      "start_time": "09:00:00",
      "end_time": "09:50:00",
      "room": "101",
      "is_conducted": false
    }
  ]
}
```

### `GET /api/attendance/teacher/sessions/{session_id}/roster`

Loads the student roster and existing attendance for an assigned class session. A session belonging to another staff member is not accessible through this route.

The response contains `session_id`, class and date details, `total_students`, `marked_students`, and `students`. Each student has `id`, `name`, `roll_number`, and the current `attendance_id`, `status`, and `remarks` (null when not yet marked).

### `PUT /api/attendance/teacher/sessions/{session_id}/attendance`

Saves attendance for the specified assigned session. The session ID comes from the class selected in the first endpoint; do not send a session ID in the request body. Submit one record per student to be marked:

```json
{
  "records": [
    { "student_id": 101, "status": "PRESENT", "remarks": null },
    { "student_id": 102, "status": "ABSENT", "remarks": "Not present" }
  ]
}
```

Allowed statuses are `PRESENT`, `ABSENT`, `LATE`, and `EXCUSED`. Re-sending a student updates their existing attendance record, so the frontend can retry or correct a mark without creating duplicates. The backend rejects duplicate student IDs in one request and students who do not belong to the selected class. Saving attendance marks the class session as conducted.

The legacy attendance create, bulk-create, update, and delete routes are administrator-only. Teachers should use the assigned-class routes above.

## Attendance by academic year

Attendance is assigned the academic year configured on the grade linked to the session's timetable. The client does not send the year when marking attendance. Existing attendance rows are backfilled from their session's timetable grade when possible; older rows without a grade/year mapping keep a null academic year.

`GET /api/attendance` returns all years unless the optional `academic_year` query parameter is supplied. Student attendance reports default to the single active academic year matching the student's current grade and section. When moving to a new academic year, activate the new grade/year and deactivate the previous one. If no active year or multiple active years match, the report returns `409`; provide `academic_year` to select a year explicitly.

Use `GET /api/attendance/student-report?roll_number=STU-101` for the student's current year, or include `academic_year` to view a previous year:

```http
GET /api/attendance/student-report?roll_number=STU-101&academic_year=2025-2026
```

The response includes the selected `academic_year`. Each attendance record also includes its academic year. The report counts and percentage only include records from the selected year.

## Exams and marks

All exam creation, editing, subject configuration, scheduling, publication, deletion, roster synchronization, and mark corrections require an authenticated admin. The `grade_id` identifies the existing active class row (grade, section, and academic year). At exam creation, the backend snapshots active students matching that class. While the exam is a draft, an admin can refresh the snapshot with `POST /api/exams/{exam_id}/roster/sync`; this adds newly eligible students without removing historical roster entries.

Create an exam:

```http
POST /api/exams
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "name": "Quarterly Examination",
  "academic_year": "2026-2027",
  "grade_id": 12,
  "description": "Term one assessment",
  "start_date": "2026-10-12",
  "end_date": "2026-10-20"
}
```

Multiple exams may use the same class and academic year. Each exam subject is configured independently and has one assigned active staff evaluator:

```http
POST /api/exams/42/subjects
```

```json
{
  "subject_id": 5,
  "max_marks": 100,
  "pass_marks": 35,
  "exam_date": "2026-10-14",
  "evaluator_staff_id": 18
}
```

Configure all subjects and assigned evaluators before scheduling. Exam details and subject marks/date settings can only be edited while the exam is a draft. An admin may reassign a scheduled subject's evaluator until that subject's evaluation is completed. Subject entries cannot be duplicated within an exam. Schedule using `POST /api/exams/{exam_id}/schedule`; the exam must have configured subjects and a non-empty roster.

Evaluators call `GET /api/exams/assigned` to list their assignments and load their roster with `GET /api/exams/assigned/subjects/{exam_subject_id}/roster`. Roster rows include any existing mark and absence status. Enter or update a student's marks with:

```http
PUT /api/exams/assigned/subjects/61/marks/203
```

```json
{
  "marks_obtained": 78.5,
  "is_absent": false,
  "remarks": "Optional note"
}
```

For an absent student, send `"marks_obtained": null` and `"is_absent": true`. Marks must be between zero and the subject maximum. Evaluators can complete a subject only after every roster student has a mark or an absence entry. Completed evaluations are locked; all completed subjects move the exam to `completed`.

Admins can review progress using `GET /api/exams/{exam_id}/progress` and publish only after all students' subject results are complete using `POST /api/exams/{exam_id}/publish`. `GET /api/exams/results/{exam_id}` accepts optional pagination (`limit` defaults to 100; maximum 500). It returns all exam results to admins, only assigned subject results to assigned staff, and only the requesting student's result after publication. Admin corrections use `PUT /api/exams/exam-subjects/{exam_subject_id}/marks/{student_id}/correction` and require a non-blank reason; old and new values, actor, timestamp, and reason are stored in the marks audit log.

Students can list exams in their own roster using `GET /api/exams/student`; the response excludes draft exams and is scoped to the authenticated student's linked profile. Published marks remain available only through the student-scoped results endpoint.
Students can view configured subject maximum marks, passing marks, and exam dates using `GET /api/exams/student/{exam_id}/subjects`; access is limited to exams in their own roster.

The standard admin publish action remains available after all evaluations are completed. Admins can instead use `POST /api/exams/{exam_id}/publish-override` on a scheduled exam after at least one mark has been entered. This publishes entered marks immediately; missing marks remain unavailable, and staff evaluation is locked.

The schema bootstrap creates the exam, roster, subject assignment, marks, and audit tables automatically on startup.

When creating or updating users, `person_id` must reference an existing student for student accounts or an existing staff record for `staff` accounts.