'''
TO DO:
1. Fix ranks not showing up in matchmaking
2. Fix buttons showing failed interactions but no failed interactions detected
3. Add RP loss/gain to matches, implement algorithm to calculate fair loss/gain
4. Add algorithm to implement skill-based matchmaking, while still randomizing 
5. Fix reshuffle not actually shuffling, + make random more random
6. Add match history, along with /career showing personal history, + all time high ELO
7. Duo/trio queue
'''
import discord
import random
import sqlite3
from discord import app_commands
from discord.ext import commands
from .views import QueueView, TeamSelectView, MatchView

queue = []
initial_queue = []
teams = []
teams_data = [
    ("JTEKT Stings", "<:JTEKT:1266599811327594568>"),
    ("Panasonic Panthers", "<:Panthers:1266599797994029127>"),
    ("JT Thunders Hiroshima", "<:Thunders:1266599787294232669>"),
    ("Toray Arrows", "<:Arrows:1266599777265778833>"),
    ("Wolfdogs Nagoya", "<:WolfDogs:1266599765571797032>"),
    ("Tokyo Great Bears", "<:Bears:1266599753932865619>"),
    ("Oita Miyoshi Weisse Adler", "<:Oita:1266599711503155301>"),
    ("VC Nagano Tridents", "<:Tridents:1266599699528552589>"),
    ("Suntory Sunbirds", "<:Sunbirds:1266599688887468062>"),
    ("Sakai Blazers", "<:Blazers:1266599648643256320>"),
    ("Vero Volley Monza", "<:VeroVolley:1266599633912860702>")
]

RANKS = [
    (0, "Bronze 1", "<:Bronze1:1268021708766314537>"),
    (100, "Bronze 2", "<:Bronze2:1268021709810831442>"),
    (200, "Bronze 3", "<:Bronze3:1268021711283163261>"),
    (300, "Silver 1", "<:Silver1:1268021730018857011>"),
    (400, "Silver 2", "<:Silver2:1268021862416252999>"),
    (500, "Silver 3", "<:Silver3:1268021860982063174>"),
    (600, "Gold 1", "<:Gold1:1268021856640827433>"),
    (700, "Gold 2", "<:Gold2:1268021719961174197>"),
    (800, "Gold 3", "<:Gold3:1268021857970552902>"),
    (900, "Platinum 1", "<:Plat1:1268021723517816889>"),
    (1000, "Platinum 2", "<:Plat2:1268021859467792495>"),
    (1100, "Platinum 3", "<:Plat3:1268021726965665884>"),
    (1200, "Diamond 1", "<:Diamond1:1268021713388572704>"),
    (1300, "Diamond 2", "<:Diamond2:1268021714831282267>"),
    (1400, "Diamond 3", "<:Diamond3:1268021715938840636>"),
    (1500, "Elite", "<:Master:1268021716756598825>"),
    (1600, "Champion", "<:Grandmaster:1268021712793108561>"),
    (1700, "Grand Champion", "<:Challenger:1268021733764497523>"),
    (1800, "Unranked", "<:Unranked:1268057325772734584>")  # Add unranked at the end
]

def create_connection():
    connection = None
    try:
        connection = sqlite3.connect("discord_bot.db")
        return connection
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return connection

def get_rank(rp):
    for threshold, rank, icon in reversed(RANKS):
        if rp >= threshold:
            return rank, icon, threshold
    return "Unranked", "<:Unranked:1268057325772734584>", 0

class QueueCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue_message = None
        self.mode = 'Full Court'
        self.team_names = []
        self.matchups = []
        self.match_messages = []
        self.conn = create_connection()
        self.create_tables()

    def create_tables(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    rp INTEGER DEFAULT 500
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY,
                    match_id TEXT NOT NULL,
                    team1 TEXT NOT NULL,
                    team2 TEXT NOT NULL,
                    winner TEXT
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY,
                    team_name TEXT NOT NULL,
                    player TEXT NOT NULL
                );
            ''')
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating tables: {e}")

    @app_commands.command(name="queue", description="Manage the queue")
    async def queue(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Queue", description="Current players in queue:\n" + "\n".join(queue) if queue else "No players in queue.")
        await interaction.response.send_message(embed=embed, view=QueueView())
        self.queue_message = await interaction.original_response()

    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(f"The coin landed on: {result}")

    @app_commands.command(name="rank", description="Display your rank or another player's rank")
    async def rank(self, interaction: discord.Interaction, player: discord.Member = None):
        try:
            if player is None:
                player = interaction.user

            user_id = player.id
            cursor = self.conn.cursor()
            cursor.execute("SELECT rp FROM players WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()

            if result:
                rp = result[0]
                rank, icon, threshold = get_rank(rp)
                next_rank_threshold = next((t for t, r, i in RANKS if t > rp), rp)
                rp_to_next_rank = next_rank_threshold - rp

                embed = discord.Embed(title=f"{player.display_name}'s Rank")
                embed.set_thumbnail(url=player.display_avatar.url)
                embed.add_field(name="Rank", value=f"{rank} {icon}", inline=True)
                embed.add_field(name="RP", value=f"{rp}/{next_rank_threshold} (Next Rank: {rp_to_next_rank} RP)", inline=True)

                await interaction.response.send_message(embed=embed)
            else:
                print(f"Player with user_id {user_id} not found in database.")
                await interaction.response.send_message("Player is not registered in the database.", ephemeral=True)
        except Exception as e:
            print(f"Error in rank command: {e}")
            await interaction.response.send_message("An error occurred while retrieving the rank.", ephemeral=True)

    def add_player(self, user_id, username):
        cursor = self.conn.cursor()
        if username.startswith("Bot "):
            cursor.execute("INSERT OR IGNORE INTO players (user_id, username) VALUES (?, ?)", (user_id, username))
        else:
            cursor.execute("INSERT OR IGNORE INTO players (user_id, username, rp) VALUES (?, ?, 500)", (user_id, username))
        self.conn.commit()

    def record_match(self, match_id, team1, team2, winner):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO matches (match_id, team1, team2, winner) VALUES (?, ?, ?, ?)", (match_id, team1, team2, winner))
        self.conn.commit()

    async def update_queue_message(self):
        try:
            if self.queue_message:
                queue_description = "Current players in queue:\n"
                cursor = self.conn.cursor()
                for player in queue:
                    cursor.execute("SELECT rp FROM players WHERE username = ?", (player,))
                    result = cursor.fetchone()
                    if result:
                        rp = result[0]
                        rank, icon, _ = get_rank(rp)
                        queue_description += f"{player} - {rank} {icon} (RP: {rp})\n"
                    else:
                        queue_description += f"{player} - Unranked <:Unranked:1268057325772734584>\n"

                embed = discord.Embed(title="Queue", description=queue_description if queue else "No players in queue.")
                await self.queue_message.edit(embed=embed, view=QueueView())
        except Exception as e:
            print(f"Error in update_queue_message: {e}")

    async def join_queue(self, interaction: discord.Interaction):
        try:
            print(f"User {interaction.user.display_name} is trying to join the queue.")
            if interaction.user.display_name not in queue:
                queue.append(interaction.user.display_name)
                self.add_player(interaction.user.id, interaction.user.display_name)
                await interaction.response.send_message(f"{interaction.user.display_name} has joined the queue!", ephemeral=True)
                await self.update_queue_message()
                print(f"User {interaction.user.display_name} joined the queue successfully.")
            else:
                print(f"User {interaction.user.display_name} is already in the queue.")
                await interaction.response.send_message("You are already in the queue.", ephemeral=True)
        except Exception as e:
            print(f"Error in join_queue: {e}")
            await interaction.response.send_message("An error occurred while trying to join the queue.", ephemeral=True)

    async def leave_queue(self, interaction: discord.Interaction):
        try:
            if interaction.user.display_name in queue:
                queue.remove(interaction.user.display_name)
                await interaction.response.send_message(f"{interaction.user.display_name} has left the queue!", ephemeral=True)
                await self.update_queue_message()
            else:
                await interaction.response.send_message("You are not in the queue.", ephemeral=True)
        except Exception as e:
            print(f"Error in leave_queue: {e}")
            await interaction.response.send_message("An error occurred while trying to leave the queue.", ephemeral=True)

    async def start_queue(self, interaction: discord.Interaction):
        print(f"Starting queue initiated by {interaction.user.display_name}")
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to start the queue.", ephemeral=True)
            return

        if len(queue) < 6:
            await interaction.response.send_message("There must be at least 6 players to start the queue.", ephemeral=True)
            return

        global initial_queue
        initial_queue = queue.copy()
        print("Queue started successfully")
        await interaction.response.send_message("Select the number of teams:", view=TeamSelectView(self.bot, mode=self.mode), ephemeral=True)

    async def handle_team_selection(self, interaction: discord.Interaction, num_teams: int):
        print(f"Handling team selection: {num_teams} teams")
        global initial_queue, teams
        max_team_size = 6 if self.mode == 'Full Court' else 4
        teams = [initial_queue[i::num_teams] for i in range(num_teams)]
        for team in teams:
            if len(team) > max_team_size:
                await interaction.response.send_message(f"Cannot form teams. Too many players for {self.mode}.", ephemeral=True)
                return

        self.team_names = random.sample(teams_data, num_teams)

        # Store team information in the database
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM teams")
        for i, team in enumerate(teams):
            team_name, _ = self.team_names[i]
            for player in team:
                cursor.execute("INSERT INTO teams (team_name, player) VALUES (?, ?)", (team_name, player))
        self.conn.commit()

        print(f"Teams formed: {teams}")
        await self.matchmake(interaction, num_teams)

    async def reshuffle_teams(self, interaction: discord.Interaction, num_teams: int):
        print(f"Reshuffling teams: {num_teams} teams")
        global teams
        max_team_size = 6 if self.mode == 'Full Court' else 4
        teams = [initial_queue[i::num_teams] for i in range(num_teams)]
        for team in teams:
            if len(team) > max_team_size:
                await interaction.response.send_message(f"Cannot form teams. Too many players for {self.mode}.", ephemeral=True)
                return

        self.team_names = random.sample(teams_data, num_teams)

        team_embed = discord.Embed(title="Teams", description="Teams reshuffled:")
        for i, team in enumerate(teams):
            team_name, emote = self.team_names[i]
            team_rp = []
            player_descriptions = []
            for player in team:
                cursor = self.conn.cursor()
                cursor.execute("SELECT rp FROM players WHERE username = ?", (player,))
                result = cursor.fetchone()
                if result:
                    rp = result[0]
                    rank, icon, _ = get_rank(rp)
                    team_rp.append(rp)
                    player_descriptions.append(f"{player} - {rank} {icon} (RP: {rp})")
                else:
                    player_descriptions.append(f"{player} - Unranked <:Unranked:1268057325772734584>")
            avg_elo = sum(team_rp) // len(team_rp) if team_rp else 0
            team_embed.add_field(name=f"{team_name} {emote} | Average ELO: {avg_elo}", value="\n".join(player_descriptions), inline=False)

        await interaction.response.send_message(embed=team_embed, view=TeamSelectView(self.bot, mode=self.mode, num_teams=num_teams))

    async def matchmake(self, interaction: discord.Interaction, num_teams: int):
        try:
            print(f"Matchmaking: {num_teams} teams")
            if not teams or len(teams) < 2:
                await interaction.response.send_message("Not enough teams to matchmake.", ephemeral=True)
                return

            print(f"Teams before shuffling: {teams}")
            random.shuffle(teams)
            print(f"Teams after shuffling: {teams}")

            self.matchups = [(self.team_names[i], self.team_names[i+1]) for i in range(0, len(self.team_names)-1, 2)]
            if len(self.team_names) % 2 == 1:
                self.matchups.append((self.team_names[-1], None))

            print(f"Matchups: {self.matchups}")

            self.match_messages = []
            for i, (team1, team2) in enumerate(self.matchups):
                team1_name, team1_emote = team1
                team2_name, team2_emote = team2 if team2 else ("No opponent", "")

                # Calculate team average ELO
                team1_elo = self.calculate_team_elo(team1_name)
                team2_elo = self.calculate_team_elo(team2_name) if team2 else 0

                match_embed = discord.Embed(title=f"Match {i+1}")
                match_embed.add_field(name=f"{team1_name} {team1_emote} | Average ELO: {team1_elo}", value="\n".join([f"{player}" for player in teams[i*2]]), inline=False)
                if team2:
                    match_embed.add_field(name=f"{team2_name} {team2_emote} | Average ELO: {team2_elo}", value="\n".join([f"{player}" for player in teams[i*2+1]]), inline=False)

                match_message = await interaction.channel.send(embed=match_embed, view=MatchView(self.bot, [(team1, team2)], match_index=i))
                self.match_messages.append(match_message)

            print(f"Match messages: {self.match_messages}")

        except Exception as e:
            print(f"Error in matchmake: {e}")
            await interaction.response.send_message("An error occurred during matchmaking.", ephemeral=True)

    def calculate_team_elo(self, team_name):
        try:
            print(f"Calculating ELO for team: {team_name}")
            cursor = self.conn.cursor()
            cursor.execute("SELECT rp FROM players WHERE username IN (SELECT player FROM teams WHERE team_name = ?)", (team_name,))
            rps = cursor.fetchall()
            if not rps:
                print(f"No RP data found for team: {team_name}")
                return 0
            total_rp = sum(rp[0] for rp in rps)
            avg_elo = total_rp // len(rps)
            print(f"Team {team_name} average ELO: {avg_elo}")
            return avg_elo
        except Exception as e:
            print(f"Error in calculate_team_elo: {e}")
            return 0

    async def reshuffle_match(self, interaction: discord.Interaction, match_index: int):
        match = self.matchups[match_index]
        team1, team2 = match
        team1_name, team1_emote = team1
        team2_name, team2_emote = team2 if team2 else ("No opponent", "")

        if not team2:
            await interaction.response.send_message("Cannot reshuffle a match with only one team.", ephemeral=True)
            return

        # Reshuffle only the players in this match
        combined_players = teams[match_index*2] + teams[match_index*2 + 1]
        random.shuffle(combined_players)
        teams[match_index*2] = combined_players[:len(combined_players)//2]
        teams[match_index*2 + 1] = combined_players[len(combined_players)//2:]

        # Calculate team average ELO
        team1_elo = self.calculate_team_elo(team1_name)
        team2_elo = self.calculate_team_elo(team2_name)

        match_embed = discord.Embed(title=f"Match {match_index + 1}")
        match_embed.add_field(name=f"{team1_name} {team1_emote} | Average ELO: {team1_elo}", value="\n".join([f"{player}" for player in teams[match_index*2]]), inline=False)
        match_embed.add_field(name=f"{team2_name} {team2_emote} | Average ELO: {team2_elo}", value="\n".join([f"{player}" for player in teams[match_index*2+1]]), inline=False)

        await self.match_messages[match_index].edit(embed=match_embed, view=MatchView(self.bot, [(team1, team2)], match_index=match_index))
        await interaction.response.send_message(f"Match {match_index + 1} reshuffled.", ephemeral=True)

    async def select_winner(self, interaction: discord.Interaction, match_index: int, winner_index: int):
        match = self.matchups[match_index]
        winner = match[winner_index][0]
        await interaction.response.send_message(f"The winner of match {match_index + 1} is {winner}!", ephemeral=True)
        await self.match_messages[match_index].delete()
        # Record the match in the database
        self.record_match(match_id=match_index, team1=match[0][0], team2=match[1][0], winner=winner)

    async def toggle_mode(self, interaction: discord.Interaction):
        print(f"Toggling mode from {self.mode}")
        self.mode = 'Short Court' if self.mode == 'Full Court' else 'Full Court'
        await interaction.response.send_message(f"Mode changed to {self.mode}.", ephemeral=True)
        print(f"Mode toggled to {self.mode}")
        await self.start_queue(interaction)

    async def add_bots(self, interaction: discord.Interaction):
        try:
            print("Adding bots to queue")
            for i in range(1, 12):
                bot_name = f"Bot {i}"
                if bot_name not in queue:
                    queue.append(bot_name)
            await interaction.response.send_message("Added 11 bots to the queue.", ephemeral=True)
            await self.update_queue_message()
            print("Bots added successfully")
        except Exception as e:
            print(f"Error in add_bots: {e}")
            await interaction.response.send_message("An error occurred while adding bots to the queue.", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        print(f"Interaction received: {interaction.data['custom_id']}")
        if interaction.type == discord.InteractionType.component:
            if interaction.data["custom_id"] == "join_queue":
                await self.join_queue(interaction)
            elif interaction.data["custom_id"] == "leave_queue":
                await self.leave_queue(interaction)
            elif interaction.data["custom_id"] == "add_bots":
                await self.add_bots(interaction)
            elif interaction.data["custom_id"] == "start_queue":
                await self.start_queue(interaction)
            elif interaction.data["custom_id"].startswith("teams_"):
                num_teams = int(interaction.data["custom_id"].split("_")[1])
                print(f"Number of teams selected: {num_teams}")
                await self.handle_team_selection(interaction, num_teams)
            elif interaction.data["custom_id"].startswith("reshuffle_"):
                num_teams = int(interaction.data["custom_id"].split("_")[1])
                await self.reshuffle_teams(interaction, num_teams)
            elif interaction.data["custom_id"] == "toggle_mode":
                await self.toggle_mode(interaction)
            elif interaction.data["custom_id"] == "matchmake":
                await self.matchmake(interaction)
            elif interaction.data["custom_id"].startswith("winner_"):
                parts = interaction.data["custom_id"].split("_")
                match_index = int(parts[1])
                winner_index = int(parts[2]) - 1
                await self.select_winner(interaction, match_index, winner_index)

async def setup(bot):
    await bot.add_cog(QueueCog(bot))
