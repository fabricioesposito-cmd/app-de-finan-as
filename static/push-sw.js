'use strict';
// Push only: never cache financial screens, APIs, tokens or user records.
self.addEventListener('push',event=>{
 let message={title:'Clareza',body:'Abra o Clareza para consultar seu orçamento.',tag:'clareza',url:'/'};
 try{Object.assign(message,event.data?.json()||{});}catch{}
 event.waitUntil(self.registration.showNotification(message.title,{body:message.body,icon:'/icon-192.png',badge:'/icon-192.png',tag:message.tag,data:{url:'/'}}));
});
self.addEventListener('notificationclick',event=>{
 event.notification.close();
 event.waitUntil((async()=>{const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});for(const client of windows){if(new URL(client.url).origin===self.location.origin){await client.focus();return;}}await self.clients.openWindow('/');})());
});
