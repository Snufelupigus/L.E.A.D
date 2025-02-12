# L.E.A.D.
The LED Enabled Automated Database is an electronics sorting program that integrates with the DigiKey API to allow you to quickly scan or manually add components to your system. As well as led integration to allow you to create physical location indicators.

# Brief Overview
L.E.A.D. is a free, open source project designed to simplify the management of electronic component inventories. By seamlessly integrating the Digikey API, L.E.A.D. automatically fetches up-to-date component details, so you don't have to spend hours entering data manually. With its built-in LED-based visual tracking, locating parts in your storage becomes as simple as a glance. Developed with a focus on minimal setup and maximum flexibility, L.E.A.D. is perfect for makers, hobbyists, and professionals who want a hassle-free, community-driven solution for their inventory challenges. Contributions and customizations are warmly welcomed as the project evolves.

# Features
+ Digikey API Search
+ Component Cataloguing
+ Component Search
+ Physical output to integrate into physical location tracking
+ Barcode Scanning

# How It Works
## Google Web App & DigiKey API Integration
The system interfaces with DigiKey’s API via a Google Web App. When a user inputs a part number, L.E.A.D. sends a request to the Google Web App, which acts as a bridge between the software and DigiKey's API. The response includes detailed product information such as pricing, stock availability, manufacturer details, and datasheets. This data is then stored in the component catalog for future reference.

## Barcode Parsing & Manual Entry
The system supports barcode scanning to quickly decode component information. The barcode decoder extracts part numbers and quantities, which are then verified against the existing database. If a part is not found in DigiKey’s database, users are given the option to manually add it. The system also automatically assigns storage locations for newly added parts.

## LED-Based Location Identification
Each component is assigned a unique location code within the storage system. A custom LED control system communicates with an Arduino to illuminate the corresponding LED, visually guiding users to the exact location of a part. When a component is checked out, the system prompts the user to confirm its retrieval and turns off the LED once the part is replaced.

## Automated Inventory Management
The backend system maintains a component catalog in JSON format, logging stock levels, part numbers, and locations.
A low-stock alert system identifies components that are running low and flags them in the user interface.
A Bill of Materials (BOM) processing feature allows users to import BOM files, checking part availability and automatically updating stock levels.
User Interface & Control

The frontend is built using Tkinter, providing an intuitive UI for searching, adding, and managing components.
A search function enables users to filter parts by part number, location, or type.
Bulk operations allow for scanning and adding multiple parts at once.

# Setup
This guide will walk you through downloading the code from GitHub, setting up a Google Apps Script for API communication, getting a DigiKey API key, and configuring the config file to link everything together.

## Downloading and Running Program
This is a basic overview on downloading and running the program. This is for begginers feel free to ignore.

### Dowloading From GitHub
1. Click on the Code button near the top right of the page
2. Select Download zip
3. Extract the zip file
4. Run the main file to start the program

## Digikey API
To interact with DigiKey's API, you need an API key.

### Steps to Obtain a DigiKey API Key:
Create a DigiKey Developer Account:

1. Go to DigiKey [API Portal](https://developer.digikey.com)
2. Sign in or create an account.
#### Register for API Access:
1. Navigate to Organizations
2. Create new organization and name it
3. Next select "Create New Production App"
4. Name you App and enable "ProductInformation V4"
5. Save and go to view tab here you will find your Client Id and Client Secret. Save these as they are needed for the your app script

## Google Web App
The Google Apps Script acts as a bridge between your Python application and DigiKey’s API, allowing you to fetch component data.

### Create and Deploy the Google Web App
1. Go to Google [Apps Script](https://script.google.com/home)
2. Select Creat New Project
3. Copy the code from the [Google Web App Code](https://github.com/Snufelupigus/L.E.A.D./blob/main/Google%20Web%20App%20Code) and paste it into your app script
4. Fill in the Blank Client ID and Client Secret sections
![image](https://github.com/user-attachments/assets/1192769b-a223-4f01-8827-9c9283761515)
![image](https://github.com/user-attachments/assets/cf9f7677-46c9-4e79-bc68-a46394e17f38)
5. Select "Deploy" in the top right and click "New Deployment"
6. Click on "Select Type" and then click "Web App"
7. Make sure that "Execute As" is set to me, and "Who Has Access" is set to Anyone
8. Copy the Web App link and paste it into the provided space in the config.json file

# Using L.E.A.D.
After opening the program you are left on a main menu page that lists types of components in the system. As well as any that have reached low stock. Your main navigation is throught the navigation button at the top left, the Add menu allows you to manually add components and they're data. Alternatively you can scan in a barcode. The search menu is fairly self explanitory. In the add and search menues you can double click to ecit or highlight a component.



