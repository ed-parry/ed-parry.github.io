# edparry.com

Personal blog built with Hugo and hosted on GitHub Pages.

## Local Development

```bash
# Install Hugo (macOS)
brew install hugo

# Run development server
hugo server -D

# Build for production
hugo --gc --minify
```

## Writing Posts

### Titled Posts
Create a post with a title that shows a summary and "read more" link on the homepage:

```bash
hugo new posts/my-post.md
```

Add the `<!--more-->` tag in your content to define where the summary should end.

### Inline Posts
Create a short, title-less post that appears inline on the homepage:

```bash
hugo new posts/thought.md
```

Then remove the `title` field from the front matter.

## Deployment

Automatically deployed to GitHub Pages via GitHub Actions when pushing to the `main` branch.
