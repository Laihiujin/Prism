
# Deployment Steps

This document outlines the steps to deploy this Next.js application.

## Prerequisites

Before you begin, ensure you have the following installed:
- [Node.js](https://nodejs.org/) (version 18.x or later recommended)
- [npm](https://www.npmjs.com/) or [yarn](https://yarnpkg.com/)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    ```

2.  **Navigate to the project directory:**
    ```bash
    cd syn_frontend_react
    ```

3.  **Install dependencies:**
    ```bash
    npm install
    ```

## Development Server

To run the application in development mode with hot-reloading, use the following command:

```bash
npm run dev
```

The application will be available at `http://localhost:3000` (or another port if 3000 is in use).

## Building for Production

To create an optimized production build of the application, run:

```bash
npm run build
```

This command will generate a `.next` folder containing the production-ready application.

## Running in Production

After building the application, you can start the production server with:

```bash
npm start
```

The application will be served from the `.next` folder and will be available at `http://localhost:3000`.

## Environment Variables

If your application requires environment variables, create a `.env.local` file in the root of the project and add them there. For example:

```
NEXT_PUBLIC_API_URL=https://api.example.com
```

These variables will be loaded automatically by Next.js.
