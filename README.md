# ZamCulture Hub

**ZamCulture Hub** is a community-driven storytelling platform focused on Zambian culture, history, lifestyle, music, and opinion.  
It allows users to submit stories, engage through likes and comments, and features an admin moderation system to ensure quality content.

🔗 **Live Site:** *(add your Render URL here)*  
🎙 **Podcast:** Integrated via embedded player from external platform (Spotify)

---

##  Features

### 👤 User Accounts
- User registration & login
- Secure password hashing
- Session-based authentication
- User profile page
- Password change support

---

### 📝 Story System
- Submit stories with:
  - Title
  - Category
  - Content
  - Optional image upload
- Admin approval required before public display
- Category-based browsing
- Default category images if no image is uploaded
- “Read More” story pages

---

### ❤️ Engagement
- Like system (one like per user per story)
- Comment system (no approval required)
- Like counts displayed on stories
- Author attribution on stories and comments

---

### 🛠 Admin Panel
- Admin role management
- Approve or reject submitted stories
- View all pending submissions
- Admin-only navigation link

---

### 🧭 Navigation & UI
- Responsive design using **Bootstrap 5**
- Featured stories carousel
- Category dropdown with story counts
- Sticky footer layout
- Mobile-friendly layout
- Custom color theme:
  - Primary: `#387999`
  - Accent: `#6fe331`

---

### 🎧 Podcast Integration
- Embedded podcast players (Spotify & others)
- External links supported
- Dedicated section/page for podcast content

---

## 🏗 Tech Stack

### Backend
- **Python**
- **Flask**
- **SQLite** (development / MVP)
- **CS50 SQL Library**

### Frontend
- **HTML5**
- **Jinja2**
- **Bootstrap 5**
- **CSS3**

### Deployment
- **Render**
- **Gunicorn**
- **GitHub**
