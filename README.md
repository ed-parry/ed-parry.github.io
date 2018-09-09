# edparry.com

Welcome to the repository for my personal website, edparry.com

## Technologies

This is a very simple, static website consisting of a single HTML page with a few images and some SASS. It is using Webpack to compile everything together. Sadly, limitations in Github Pages means the build output of Webpack needs to be into the root directory, but all development is done within /dev.

Ordinarily, the build/distribution files wouldn't be part of the source, but as Github is also being used to host the finished product, they need to be here. **All changes should be made only within /dev**.

## How to build

The project has a dependency on Node V7.6+, and Webpack. 

Install npm dependencies

```sh
 npm install 
```

Start the development server

```sh
npm start
```

Build for production

```sh
npm run build
```

To preview the production build
```sh
npm run preview
```