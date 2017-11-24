import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { AngularFireModule } from 'angularfire2';
import { AngularFireDatabaseModule } from 'angularfire2/database';
import { AngularFireAuthModule } from 'angularfire2/auth';

import { AppComponent } from './app.component';

export const firebaseConfig = {
    apiKey: "AIzaSyCR21okk9Xv-c0hFkcxERHaai3Vt4MAT4U",
    authDomain: "genairics.firebaseapp.com",
    databaseURL: "https://genairics.firebaseio.com",
    projectId: "genairics",
    storageBucket: "genairics.appspot.com",
    messagingSenderId: "898718573823"
};
    
@NgModule({
  declarations: [
    AppComponent
  ],
  imports: [
      BrowserModule,
      AngularFireModule.initializeApp(firebaseConfig),
      AngularFireDatabaseModule,
      AngularFireAuthModule
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
