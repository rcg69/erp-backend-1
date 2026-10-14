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
| GET | `/api/user-details/{user_id}` | Admin only | Load a user's profile |
| PATCH | `/api/user-details/{user_id}` | Admin only | Update a user's profile |
| GET | `/api/attendance/teacher/classes` | Staff only | Get the signed-in teacher's assigned classes for a date |
| GET | `/api/attendance/teacher/sessions/{session_id}/roster` | Staff only | Load the class roster and existing attendance |
| PUT | `/api/attendance/teacher/sessions/{session_id}/attendance` | Assigned staff only | Save or update attendance for that class session |
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

### Admin profile access

Administrators can use `GET /api/user-details/{user_id}` to fetch and `PATCH /api/user-details/{user_id}` to edit any user's profile. Both require an administrator account. The self-service endpoints always use the authenticated user's ID and do not accept a user ID from the request.

## Students

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

`name` and `roll_number` are required. `admission_date`, `parent_name`, and `mobile_number` are optional. `admission_date` must use `YYYY-MM-DD` format. A student does not have a `user_id`.

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

When creating or updating users, `person_id` must reference an existing student for student accounts or an existing staff record for `staff` accounts.