# Instagram Report 3.0

A modern Python application that analyzes your Instagram data and tracks follower changes.

## Features

- 📊 **Follower Analysis**: Comparative analysis of incoming and outgoing followers
- 🎨 **Modern UI**: Modern interface with dark/light theme support
- 📈 **Graph Visualization**: Graphical display of follower changes
- 🔍 **Detailed Lists**: 
  - People you follow but don't follow you back
  - People who follow you but you don't follow back
  - Close friends
  - Favorites
  - Blocked profiles
  - Restricted profiles
  - Incoming/Outgoing requests
  - Removed suggestions
  - Recently unfollowed profiles
- 📅 **Date Tracking**: Track follower changes by date
- 🔄 **Auto Update**: Automatically detect new Instagram data

## Installation

### Requirements

```bash
pip install -r requirements.txt
```

### Required Libraries

```
tkinter
beautifulsoup4
matplotlib
pillow
```

## Usage

1. Download data from Instagram (ZIP format)
2. Place the ZIP file in your Downloads folder
3. Run the application:

```bash
python app.py
```

## Feature Details

### Main Tabs
- **People You Follow But Don't Follow You Back**: Users you follow but who don't follow you
- **People Who Follow You But You Don't Follow Back**: Users who follow you but you don't follow
- **Close Friends**: Your close friends list
- **Favorites**: Your favorite profiles
- **Follower Analysis**: Graphical analysis of follower changes

### Other Tabs
- Blocked profiles
- Restricted profiles
- Incoming follow requests
- Outgoing follow requests
- Removed suggestions
- Recently unfollowed profiles

### Sorting Options
- Newest to Oldest
- Oldest to Newest
- A to Z
- Z to A

## Theme Support

The application automatically detects your system theme and applies the appropriate theme:
- **Light Theme**: Modern, clean appearance
- **Dark Theme**: Dark theme that reduces eye strain

## Developer

**Can Oruckahya** - Instagram Report 3.0

## License

This project is licensed under the MIT License.

## Contributing

1. Fork the project
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request 