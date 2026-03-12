# dhlotteryCheck
Automated Lottery Analysis and Prediction Bot.

## Features
- **Lotto 6/45**: Analyzes historical 1st prize draws up to Mar 9, 2026, and uses algorithmic balancing to predict 10 optimal future combinations.
- **Pension Lottery 720+**: Crawls historical 1st, 2nd, and Bonus winning tickets to calculate 10 probable future sequences.
- **Triple Luck**: Uses rolling historical probabilistic data of recent electronic winners to recommend the optimal time of day to purchase a ticket.

## Automation Setup
The bot utilizes `PM2` to run a 24/7 background scheduler.
- **Daily at 06:00, 13:00, 19:00**: Dispatches a combined report email comprising of optimized Lotto 6/45 numbers (5 games), Pension 720+ sequences (5 games), and Triple Luck timing recommendations.

## Configuration
Requires a `.env` file at the root of this folder containing:
```
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECEIVER_EMAIL=receiver_email@gmail.com
```
