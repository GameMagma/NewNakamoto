"""This module acts as the connection between the bot and the SQL management folder. Everything outside the directory
should only interact with this module"""
import interactions
import mysql.connector

import os
from dotenv import load_dotenv

from mysql.connector import MySQLConnection

from interactions import User

load_dotenv()  # Loads the .env file


class SQLManager:
    # cnx: MySQLConnection  # The connection used to connect to the database

    def __init__(self):
        # self._connection = SQLConnection()
        print("Establishing connection to Nakamoto database...")
        self.cnx = mysql.connector.connect(user=os.getenv("SQL_USER"), password=os.getenv("SQL_PASSWORD"),
                                           host=os.getenv("SQL_HOST"), port=os.getenv("SQL_PORT"),
                                           database=os.getenv("SQL_DATABASE"))
        self.cursor = self.cnx.cursor(buffered=True)  # This is used to interact with the actual database
        print("Connection Established.\n\n")

    def is_closed(self) -> bool:
        return self.cnx.is_connected()

    def updateUser(self, user: User):
        """
        Checks to see if a user has been added to the database yet.
        :param user: user to check
        :return: True if they exist, false otherwise
        """
        query_userTable = "SELECT * FROM `users` WHERE `userID` = %s"
        self.cursor.execute(query_userTable, (int(user.id),))

        result = self.cursor.fetchone()

        if result is None:
            query_createUser = "INSERT INTO `users`(`userID`, `nickname`) VALUES (%s,%s);"
            self.cursor.execute(query_createUser, (int(user.id), str(user.username)))
            # Default in the hard database will handle favors, no need to pass it in here
            query_createWallet = "INSERT INTO `wallet`(`userID`) VALUES (%s)"
            self.cursor.execute(query_createWallet, (int(user.id),))
            self.cnx.commit()
        else:
            if str(result[1]) == str(user.username):
                return
            query_updateUser = "UPDATE users SET nickname = %s WHERE userID = %s"
            self.cursor.execute(query_updateUser, (str(user.username), str(user.id)))
            self.cnx.commit()

    def get_wallet(self, userID: int) -> tuple:
        """
        Gets the wallet of the designated user.

        :param userID: ID of the user to get
        :return: Nickname and Cryptofavors formatted in a list
        """

        # Runs query() in SQLConnection, then fetches the result from the cursor
        self.cursor.execute("SELECT * FROM wallet WHERE userID = %s", (userID,))
        return self.cursor.fetchone()

    def add_transaction(self, sender: int, receiver: int, amount: int):
        query_addTransaction = "INSERT INTO `transactions`(`sender`, `receiver`, `amount`, `status`) " \
                               "VALUES ('%s','%s','%s','PENDING')"

        self.cursor.execute(query_addTransaction, (sender, receiver, amount))

        query_selectLast = "SELECT LAST_INSERT_ID()"
        self.cursor.execute(query_selectLast)

        result = self.cursor.fetchone()[0]
        # print(f"Transaction ID in SQLManager: {result}")

        self.cnx.commit()
        return result

    def confirm_transaction(self, transaction_id: int, userID: int):
        # Find the transaction and check that it was found
        query_findTransaction = "SELECT * FROM transactions WHERE transactionID=%s"
        self.cursor.execute(query_findTransaction, (transaction_id,))
        transaction = self.cursor.fetchone()

        # Check that it exists
        if transaction is None:
            return -1
        # If the person requesting to confirm the transaction is not the original sender, error out
        elif int(transaction[1]) != userID:
            return -2
        elif transaction[4] != "PENDING":
            return -3

        # Get current timestamp to mark transaction completed with
        query_getTimestamp = "SELECT CURRENT_TIMESTAMP()"
        self.cursor.execute(query_getTimestamp)
        timestamp = self.cursor.fetchone()[0]

        query_updateTransaction = "UPDATE transactions SET status = %s, completed = %s WHERE transactionID = %s"
        self.cursor.execute(query_updateTransaction, ("COMPLETED", timestamp, transaction_id))
        self.cnx.commit()

        self.edit_favors(transaction[2], transaction[3])  # Update the receiver's favors

    def cancel_transaction(self, transaction_id: int, userID: int):
        # Find the transaction and check that it was found
        query_findTransaction = "SELECT * FROM transactions WHERE transactionID=%s"
        self.cursor.execute(query_findTransaction, (transaction_id,))
        transaction = self.cursor.fetchone()

        # Check that it exists
        if transaction is None:
            return -1
        # If the person requesting to confirm the transaction is not the original sender, error out
        elif int(transaction[1]) != userID:
            return -2
        elif transaction[4] != "PENDING":
            return -3

        query_markAsCancelled = "UPDATE transactions SET status = 'CANCELLED' WHERE transactionID = %s"
        self.cursor.execute(query_markAsCancelled, (transaction_id,))
        self.cnx.commit()

        # Refund the sender's favors
        self.edit_favors(transaction[1], transaction[3])

    def edit_favors(self, userID: int, amount: int):
        # Get the number of favors from the selected user's wallet
        query_selectWallet = "SELECT cryptofavors FROM wallet WHERE userID=%s"
        self.cursor.execute(query_selectWallet, (userID,))
        favors = self.cursor.fetchone()[0]

        # Check if the favors were retrieved correctly
        if favors is None:
            return -1
        else:
            favors += amount  # Update favors
            query_updateWallet = "UPDATE wallet SET cryptofavors = %s WHERE userID = %s"
            self.cursor.execute(query_updateWallet, (favors, userID))
            self.cnx.commit()

    def add_nomination(self, authorID: int, guildID: int, channelID: int, category: str,
                       messageID: int, message: str = None):
        """
        Adds the nomination to the database. Is this table super overcomplicated? Probably. But it works.
        :return: True if successful, False otherwise
        """

        print("Adding nomination...")

        if message is not None:
            # Prune string down to the first 255 characters or less to abide by SQL's VARCHAR limit
            message = message[:255]

        # Create query
        query_addNomination = ("INSERT INTO `nominations`(`authorID`, `guildID`, `channelID`, `messageID`, `message`,"
                               "`category`) "
                               "VALUES (%s,%s,%s,%s,%s,%s)")

        try:
            # Execute query
            self.cursor.execute(query_addNomination, (authorID, guildID, channelID, messageID, message, category))

            # Check if the nomination was added by grabbing the last inserted ID and comparing
            query_selectLast = "SELECT LAST_INSERT_ID()"
            self.cursor.execute(query_selectLast)

            # # Debugging
            # result = self.cursor.fetchone()
            # print(f"Nomination ID in SQLManager: {result[0]}")
        except Exception as e:
            print(f"Error adding nomination with messageID {messageID}: {e}")
            return False
        else:
            self.cnx.commit()
            return True

    def get_nomination(
            self, author_id: int | User = None, category: str = None,
            guild_id: int = None, channel_id: int = None, message_id: int = None) -> list[tuple]:
        """
        Gets select nominations from the database.

        :param author_id: ID of the user who nominated the message. Should be a Snowflake type.
        :param category: Category of the nomination.
        :param guild_id: ID of the guild where the nomination was made. Can be a Snowflake (int) or a User type.
        :param channel_id: ID of the channel where the nomination was made. Should be in Snowflake format
        :param message_id: ID of the message that was nominated. Should be in Snowflake format.
        :return: A list of tuples in the format of:
        [(NominationID, GuildID, ChannelID, MessageID, AuthorID, Category, message), ...] or will return None.
        """

        # Base query
        query = "SELECT * FROM nominations WHERE 1"

        # Conditions for optional parameters
        conditions = []
        if guild_id is not None:
            conditions.append(f"guildID = {guild_id}")
        if channel_id is not None:
            conditions.append(f"channelID = {channel_id}")
        if message_id is not None:
            conditions.append(f"messageID = {message_id}")
        if author_id is not None:
            if author_id is User:
                author_id = author_id.id

            conditions.append(f"authorID = {author_id}")
        if category is not None:
            conditions.append(f"category = '{category}'")

        # Combine conditions into the query
        if conditions:
            query += " AND " + " AND ".join(conditions)

        # Execute the query
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def get_categories(self) -> list:
        query_getCategories = "SELECT * FROM categories"
        self.cursor.execute(query_getCategories)
        return self.cursor.fetchall()

    def close(self):
        """Closes the connection"""

        print("Closing Connection")
        self.cursor.close()
        self.cnx.close()
        print("Connection Closed")
