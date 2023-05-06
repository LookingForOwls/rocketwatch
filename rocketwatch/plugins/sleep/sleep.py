import datetime
import logging
from io import BytesIO

import matplotlib.pyplot as plt
import requests
from discord import File
from discord.ext import commands
from discord.ext.commands import Context, hybrid_command

from utils.cfg import cfg
from utils.embeds import Embed
from utils.visibility import is_hidden

log = logging.getLogger("sleep")
log.setLevel(cfg["log_level"])


class Oura(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @hybrid_command()
    async def sleep_schedule(self, ctx: Context):
        await ctx.defer(ephemeral=is_hidden(ctx))
        e = Embed(title="Invis's Sleep Schedule")
        current_date = datetime.datetime.now()
        start_date = current_date - datetime.timedelta(days=30)
        end_date = current_date
        res = requests.get("https://api.ouraring.com/v2/usercollection/sleep",
                           params={"start_date": start_date.strftime("%Y-%m-%d"),
                                   "end_date"  : end_date.strftime("%Y-%m-%d")},
                           headers={"Authorization": f"Bearer {cfg['oura.secret']}"})
        if res.status_code != 200:
            e.description = "Error fetching sleep data"
            await ctx.send(embed=e)
            return
        data = res.json()
        if len(data["data"]) == 0:
            e.description = "No sleep data found"
            await ctx.send(embed=e)
            return

        daily_sleep = {
            (start_date + datetime.timedelta(days=i)).strftime("%Y-%m-%d"): []
            for i in range((end_date - start_date).days + 1)}

        for sleep in data["data"]:
            if sleep["type"] == "rest":
                continue
            # skip if sleep_duration is less than 30 minutes. units are in seconds
            if sleep["total_sleep_duration"] < 30 * 60:
                continue
            start_date = datetime.datetime.fromisoformat(sleep["bedtime_start"]) + datetime.timedelta(seconds=sleep["latency"])
            # the start day is the next day if we are past 12pm, otherwise it is the current day
            start_day = start_date + datetime.timedelta(days=1) if start_date.hour >= 12 else start_date
            # format to string
            start_day = start_day.strftime("%Y-%m-%d")
            end_date = start_date + datetime.timedelta(seconds=sleep["total_sleep_duration"])
            # the end day is the next day if we are past 12pm, otherwise it is the current day
            end_day = end_date + datetime.timedelta(days=1) if end_date.hour >= 12 else end_date
            # format to string
            end_day = end_day.strftime("%Y-%m-%d")
            thresh = datetime.datetime(year=end_date.year, month=end_date.month, day=end_date.day, hour=12,
                                       tzinfo=end_date.tzinfo)
            if start_day not in daily_sleep:
                daily_sleep[start_day] = []
            # weekday based on start date
            weekday = datetime.datetime.fromisoformat(start_day).weekday()
            if start_day != end_day:
                daily_sleep[start_day].append(
                    {"relative_start": start_date - (thresh - datetime.timedelta(days=1)), "duration": thresh - start_date,
                     "weekday"       : weekday})
                if end_day not in daily_sleep:
                    daily_sleep[end_day] = []
                daily_sleep[end_day].append(
                    {"relative_start": datetime.timedelta(), "duration": end_date - thresh, "weekday": weekday})
            else:
                relative_start = start_date - (thresh - datetime.timedelta(days=1))
                if relative_start >= datetime.timedelta(hours=24):
                    relative_start -= datetime.timedelta(hours=24)
                daily_sleep[start_day].append(
                    {"relative_start": relative_start, "duration": end_date - start_date, "weekday": weekday})
        log.debug(daily_sleep)
        # sort by date
        daily_sleep = dict(sorted(daily_sleep.items(), key=lambda x: x[0]))
        day_of_week_colors = ["#ff0000", "#ff8000", "#ffff00", "#80ff00", "#00ff00", "#00ff80", "#00ffff"]
        # plot
        fig, ax = plt.subplots()
        for i, (day, sleeps) in enumerate(daily_sleep.items()):
            # plot each sleep, from top to bottom
            for sleep in sleeps:
                color = day_of_week_colors[sleep["weekday"]]
                ax.bar(i, sleep["duration"].total_seconds() / 3600, bottom=((24 * 60 * 60) - sleep[
                    "relative_start"].total_seconds() - sleep["duration"].total_seconds()) / 3600, color=color)
        # set x axis labels, only every 7th day
        ax.set_xticks(range(0, len(daily_sleep), 7))
        ax.set_xticklabels([day for i, (day, _) in enumerate(daily_sleep.items()) if i % 7 == 0])
        # set y axis labels
        ax.set_yticks(range(0, 25, 2))
        ax.set_yticklabels([f"{i}:00" if i >= 0 else f"{24 + i}:00" for i in range(12, -13, -2)])
        # set y limit
        ax.set_ylim(0, 24)
        # grid
        ax.grid(True)
        # set title
        ax.set_title("Invis's Sleep Schedule")

        # reduce padding
        plt.tight_layout()

        img = BytesIO()
        fig.savefig(img, format='png')
        img.seek(0)
        plt.close()

        e.set_image(url="attachment://sleep.png")
        buf = File(img, filename="sleep.png")
        # send image
        await ctx.send(file=buf, embed=e)


async def setup(bot):
    await bot.add_cog(Oura(bot))
