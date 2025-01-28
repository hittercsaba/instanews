
# InstaNews

InstaNews is an open-source, lightweight news aggregator that simplifies the process of gathering news from multiple sources. The application allows you to add base URLs for news domains, and it automatically discovers the associated Atom or RSS feeds. You can add unlimited sources and enjoy reading the news without classification or filtering.

---

## About the Project

InstaNews aims to provide a straightforward and user-friendly way to gather and read news from your favorite sources. Built with simplicity in mind, it enables users to add and manage their own news sources without any complicated setup or AI-driven filtering. This project is a practical tool for those who prefer full control over their news feeds and want a clean, minimalistic platform to stay updated.

---

## Features

- **Automatic Feed Discovery**: Add a base URL for any news domain, and the app will automatically find the Atom or RSS feed.
- **Unlimited Sources**: Add as many sources as you like to curate your personal news aggregator.
- **Simple Reading Experience**: Enjoy a clean interface to browse and read the latest news from your added sources.
- **Open Source**: Built with Python and Flask, encouraging collaboration and contributions from the community.

---

## Getting Started

### Prerequisites

Ensure you have the following installed:

- **Python 3.8 or later**
- **pip** (Python package manager)

### Installation

1. Clone the repository:
   ```bash
   git clone git@github.com:hittercsaba/instanews.git
   cd instanews
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   - **Windows**:
     ```bash
     venv\Scripts\activate
     ```
   - **macOS/Linux**:
     ```bash
     source venv/bin/activate
     ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Run the application:
   ```bash
   python app.py
   ```

6. Access the platform in your web browser:
   ```text
   http://localhost:5090
   ```

---

## How to Use

1. Add a base URL for a news website using the application’s interface.
2. InstaNews will automatically discover the Atom or RSS feed from the URL.
3. Add unlimited sources to create your personal feed.
4. Browse and read the latest news directly within the app.

---

## Contributing

Contributions are welcome and encouraged! Here’s how you can help:

1. Fork the repository.
2. Create a feature branch:
   ```bash
   git checkout -b feature/new-feature
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add new feature"
   ```
4. Push your branch:
   ```bash
   git push origin feature/new-feature
   ```
5. Open a Pull Request.

---

## License

This project is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)** license.  
You are free to:
- Share — copy and redistribute the material in any medium or format.
- Adapt — remix, transform, and build upon the material.

**However, commercial use is strictly prohibited**.

---

## About the Author

### Hitter Csaba, PhD Candidate  
**Independent Consultant in Digital Transformation & e-Governance**  
- As an experienced Chief Technology Officer and e-Governance expert, I am passionate about creating user-centered services for public administration.
- With over 21 years in the IT industry and 10+ years dedicated to public administration projects, I specialize in IT Service Management, Project Management, and open-source advocacy.
- I believe in leveraging technology to enhance efficiency, transparency, and citizen engagement.

Feel free to contact me on csaba.hitter@gmail.com

---

## Vision

InstaNews is built on the belief that accessing news should be simple, unrestricted, and user-driven. By enabling users to manage their own news sources, we aim to empower individuals to stay informed on their terms. Together, let’s foster a more open and connected digital world.
