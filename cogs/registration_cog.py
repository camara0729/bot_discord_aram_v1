# cogs/registration_cog.py
import os
import discord
from discord.ext import commands
from discord import app_commands
import requests
import database as db

RIOT_API_KEY = os.getenv("RIOT_API_KEY")

class RegistrationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="registrar", description="Associa sua conta do Discord a uma conta Riot.")
    @app_commands.describe(riot_id="Seu Riot ID completo (ex: Nome#TAG).")
    async def register(self, interaction: discord.Interaction, riot_id: str):
        await interaction.response.defer(ephemeral=True)

        if '#' not in riot_id:
            await interaction.followup.send("Formato de Riot ID inválido. Use o formato `Nome#TAG`.", ephemeral=True)
            return

        game_name, tag_line = riot_id.split('#', 1)
        
        if db.get_player_by_discord_id(interaction.user.id):
            await interaction.followup.send("Você já está registrado.", ephemeral=True)
            return

        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        headers = {"X-Riot-Token": RIOT_API_KEY}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            account_data = response.json()
            puuid = account_data.get('puuid')

            if not puuid:
                await interaction.followup.send("Não foi possível encontrar uma conta Riot com esse ID.", ephemeral=True)
                return

            success = db.add_player(interaction.user.id, puuid, riot_id)
            if success:
                await interaction.followup.send(f"Conta `{riot_id}` registrada com sucesso!", ephemeral=True)
            else:
                await interaction.followup.send("Esta conta Riot ou do Discord já foi registrada.", ephemeral=True)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                await interaction.followup.send("Conta Riot não encontrada. Verifique o nome e a tag.", ephemeral=True)
            else:
                await interaction.followup.send(f"Erro ao contatar a API da Riot: {e.response.status_code}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Ocorreu um erro inesperado: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot))