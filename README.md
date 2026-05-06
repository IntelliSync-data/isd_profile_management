# ISD Profile Management System

A comprehensive Profile Management System for Odoo 18.0 that allows managers to create profiles with steps and assign them to users (students) for completion tracking and payment management.

## Features

### User Features (Students)
- **Login & Authentication**: Secure login with forgot password support
- **Profile Management**: View assigned profiles and select profiles to work on
- **Step Selection**: Choose required steps with cost calculation
- **Payment Processing**: Make payments with receipt upload
- **Progress Tracking**: Monitor completion status and deadlines
- **Status Management**: Track profile and step statuses

### Manager Features
- **User Management**: Create and manage student accounts
- **Profile Creation**: Design profiles with customizable steps
- **Assignment Management**: Assign profiles to users
- **Payment Confirmation**: Review and confirm student payments
- **Progress Monitoring**: Track user progress across all profiles
- **Reporting**: Generate comprehensive reports

### Additional Features
- **Notification System**: Automated notifications for updates
- **Security**: Role-based access control
- **Reporting**: Detailed progress and financial reports
- **Responsive UI**: User-friendly interface for all devices

## Installation

1. Copy the module to your Odoo addons directory
2. Update the apps list in Odoo
3. Install the "ISD Profile Management" module
4. Configure user groups (Student/Manager)
5. Create your first profile with steps

## Usage

### For Managers
1. Create profiles with detailed steps
2. Assign profiles to students
3. Monitor student progress
4. Confirm payments when receipts are uploaded
5. Generate reports for analysis

### For Students
1. View assigned profiles
2. Select steps you want to complete
3. Calculate total cost and make payment
4. Upload payment receipt
5. Track your progress and complete steps

## Models

- **Profile Management**: Main profile container
- **Profile Step**: Individual steps within profiles
- **User Profile**: Assignment of profiles to users
- **User Step**: User's progress on individual steps
- **Profile Payment**: Payment tracking and confirmation

## Security Groups

- **Student**: Can view and manage their own profiles
- **Manager**: Full access to all profile management features

## Requirements

- Odoo 18.0
- Base modules: base, mail, web, portal

## Support

For issues and feature requests, please contact the development team.