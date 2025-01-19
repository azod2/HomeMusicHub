<template>

<div class="app">
<h1>HomeMusicHub</h1>
<div>
<input
type="text"
placeholder="Enter YouTube/Bilibili URL"
v-model="youtubeUrl"
/>
<button @click="handlePlayYouTube">Play YouTube/Bilibili</button>
</div>
<h2>Music List</h2>
<ul>
<li v-for="filename in musicList" :key="filename">
{{ filename }}
<button @click="handlePlay(filename)">Play</button>
</li>
</ul>
<p v-if="playing">Playing: {{ currentSong }}</p>
<button @click="handleStop" :disabled="!playing">Stop</button>
<audio ref="audioPlayer" controls :src="audioUrl" :key="audioUrl" v-if="audioUrl"></audio>
</div>
</template>

<script>
import axios from 'axios';
import { nextTick } from 'vue';
const API_URL = 'http://192.168.50.40:5000';

export default {
  data() {
    return {
      musicList: [],
      youtubeUrl: '',
       playing: false,
      currentSong: '',
       audioUrl:'',
    };
  },
    mounted() {
        this.fetchMusicList();
    },
  methods: {
     async fetchMusicList() {
          try {
              const response = await axios.get(`${API_URL}/music`);
              this.musicList = response.data;
          } catch (error) {
              console.error('Error fetching music list:', error);
          }
      },
    async handlePlay(filename) {
      try {
        const response = await axios.post(`${API_URL}/play`, { filename });

       console.log("response:", response); // 加入這一行
       console.log("response.data:", response.data); // 加入這一行
       console.log("response.data.audioUrl:", response.data.audioUrl); // 加入這一行

        //this.audioUrl = response.data.audioUrl;
        this.audioUrl = `${API_URL}${response.data.audioUrl}`;
        this.playing = true;
        this.currentSong = filename;
          await nextTick()
          this.$refs.audioPlayer.play()
      } catch (error) {
        console.error('Error playing music:', error);
      }
    },
     async handleStop() {
        try {
            await axios.post(`${API_URL}/stop`);
             this.playing = false;
             this.currentSong = '';
             this.audioUrl = '';
        } catch (error) {
           console.error('Error stopping music:', error);
        }
    },
     async handlePlayYouTube() {
          try {
              const response = await axios.post(`${API_URL}/play_youtube`, { url: this.youtubeUrl });
              this.audioUrl = response.data.audioUrl;
             this.playing = true;
            this.currentSong = this.youtubeUrl;
              await nextTick()
             this.$refs.audioPlayer.play()
        } catch (error) {
            console.error('Error playing YouTube:', error);
        }
      },
    },
  };
</script>

<style>
.app {
  font-family: sans-serif;
  text-align: center;
}
</style>
