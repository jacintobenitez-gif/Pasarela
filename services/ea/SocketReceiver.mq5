//+------------------------------------------------------------------+
//|                                             SocketReceiver.mq5   |
//|                 Simple EA para recibir mensajes por socket TCP   |
//|  v1.01 (readfix): corrige el orden de parámetros en SocketRead   |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025"
#property link      "https://www.mql5.com"
#property version   "1.01"
#property strict

input string SocketHost      = "127.0.0.1"; // IP del servidor Python
input int    SocketPort      = 8888;        // Puerto del servidor Python
input int    ConnectTimeout  = 5000;        // Timeout de conexión en ms
input int    ReconnectDelay  = 5;           // Segundos entre reintentos
input bool   ShowAlerts      = false;       // Mostrar Alert() al recibir
input bool   ShowComment     = true;        // Mostrar en Comment()

int      socketHandle   = INVALID_HANDLE;
datetime lastReconnect  = 0;
string   pendingBuffer  = "";
int      messageCount   = 0;
string   lastMessage    = "";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("SocketReceiver MT5 iniciado (v1.01-readfix).");
   EventSetTimer(1); // timer cada segundo
   AttemptConnect(); // Intentar conectar inmediatamente
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   if(socketHandle != INVALID_HANDLE)
   {
      SocketClose(socketHandle);
      socketHandle = INVALID_HANDLE;
   }
   Comment("");
   Print("SocketReceiver MT5 detenido.");
}

//+------------------------------------------------------------------+
//| Timer event                                                       |
//+------------------------------------------------------------------+
void OnTimer()
{
   datetime now = TimeCurrent();

   if(socketHandle == INVALID_HANDLE)
   {
      if(now - lastReconnect >= ReconnectDelay)
      {
         AttemptConnect();
         lastReconnect = now;
      }
      UpdateDisplay();
      return;
   }

   if(!SocketIsConnected(socketHandle))
   {
      Print("[SocketReceiver] Conexión perdida. Reintentando...");
      SocketClose(socketHandle);
      socketHandle = INVALID_HANDLE;
      UpdateDisplay();
      return;
   }

   ReceiveMessages();
   UpdateDisplay();
}

//+------------------------------------------------------------------+
//| Intentar conexión                                                 |
//+------------------------------------------------------------------+
void AttemptConnect()
{
   if(socketHandle != INVALID_HANDLE)
   {
      SocketClose(socketHandle);
      socketHandle = INVALID_HANDLE;
   }

   socketHandle = SocketCreate();
   if(socketHandle == INVALID_HANDLE)
   {
      uint err = GetLastError();
      Print("[SocketReceiver] ❌ Error al crear socket: ", err);
      return;
   }

   Print("[SocketReceiver] Socket creado. Handle: ", socketHandle);
   Print("[SocketReceiver] Intentando conectar a '", SocketHost, "':", SocketPort, " (timeout: ", ConnectTimeout, "ms)...");
   
   bool connected = SocketConnect(socketHandle, SocketHost, SocketPort, ConnectTimeout);
   if(!connected)
   {
      uint err = GetLastError();
      Print("[SocketReceiver] ❌ SocketConnect falló. Error: ", err);
      Print("[SocketReceiver] Host: '", SocketHost, "' Port: ", SocketPort);
      SocketClose(socketHandle);
      socketHandle = INVALID_HANDLE;
      return;
   }

   Print("[SocketReceiver] ✅ Conectado exitosamente");
   
   // Configurar timeouts para lectura/escritura (1 segundo)
   SocketTimeouts(socketHandle, 1000, 1000);
   
   messageCount = 0;
   pendingBuffer = "";
}

//+------------------------------------------------------------------+
//| Leer mensajes pendientes  (v1.01-readfix)                        |
//+------------------------------------------------------------------+
void ReceiveMessages()
{
   if(socketHandle == INVALID_HANDLE)
      return;

   uint readable = SocketIsReadable(socketHandle);
   if(readable > 0)
   {
      Print("[SocketReceiver] 📥 Datos disponibles: ", readable, " bytes");
      
      // Buffer más grande que los datos disponibles
      uchar buffer[];
      uint bufferSize = readable + 100;
      ArrayResize(buffer, (int)bufferSize);
      
      ResetLastError();
      
      // ✅ FIX: maxlen = readable, timeout = 1000 ms
      int received = SocketRead(socketHandle, buffer, readable, 1000);
      uint err = GetLastError();
      
      Print("[SocketReceiver] SocketRead: received=", received, ", error=", err, ", readable=", readable, ", bufferSize=", bufferSize);

      if(received > 0)
      {
         Print("[SocketReceiver] 📨 Leídos ", received, " bytes del socket");
         string chunk = CharArrayToString(buffer, 0, received);
         Print("[SocketReceiver] 📝 Contenido recibido: '", chunk, "'");
         pendingBuffer += chunk;

         int pos = StringFind(pendingBuffer, "\n");
         while(pos >= 0)
         {
            string line = StringSubstr(pendingBuffer, 0, pos);
            pendingBuffer = StringSubstr(pendingBuffer, pos + 1);

            if(StringLen(line) > 0)
            {
               Print("[SocketReceiver] 🔔 Procesando línea completa: '", line, "'");
               ProcessMessage(line);
            }

            pos = StringFind(pendingBuffer, "\n");
         }
      }
      else if(received == 0 && err == 0)
      {
         // Caso especial: SocketRead retorna 0 sin error pero se reportan bytes
         Print("[SocketReceiver] ⚠️ SocketRead=0 sin error pero hay datos. Intentando leer con buffer más grande...");
         
         // Intentar con un buffer mucho más grande
         ArrayResize(buffer, 2048);
         ResetLastError();

         // ✅ FIX: maxlen = 2048, timeout = 1000 ms
         received = SocketRead(socketHandle, buffer, 2048, 1000);
         err = GetLastError();
         Print("[SocketReceiver] Segundo intento: received=", received, ", error=", err);
         
         if(received > 0)
         {
            string chunk = CharArrayToString(buffer, 0, received);
            Print("[SocketReceiver] 📝 Contenido (segundo intento): '", chunk, "'");
            pendingBuffer += chunk;
            
            int pos = StringFind(pendingBuffer, "\n");
            while(pos >= 0)
            {
               string line = StringSubstr(pendingBuffer, 0, pos);
               pendingBuffer = StringSubstr(pendingBuffer, pos + 1);
               if(StringLen(line) > 0)
               {
                  ProcessMessage(line);
               }
               pos = StringFind(pendingBuffer, "\n");
            }
         }
         else
         {
            // Sonda 1 byte (opcional)
            uchar probe[];
            ArrayResize(probe, 1);
            ResetLastError();
            // ✅ FIX: maxlen = 1, timeout = 100 ms
            int r1 = SocketRead(socketHandle, probe, 1, 100);
            uint e1 = GetLastError();
            Print("[SocketReceiver] Sonda 1 byte: received=", r1, ", error=", e1);
         }
      }
      else
      {
         Print("[SocketReceiver] ⚠️ SocketRead falló. received=", received, ", error=", err);
      }
   }
}

//+------------------------------------------------------------------+
//| Procesar un mensaje recibido                                      |
//+------------------------------------------------------------------+
void ProcessMessage(string msg)
{
   messageCount++;
   string timestamp = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
   Print("[SocketReceiver] ✅ [", timestamp, "] Mensaje #", IntegerToString(messageCount), ": ", msg);

   if(ShowAlerts)
      Alert("SocketReceiver: ", msg);

   lastMessage = msg;
}

//+------------------------------------------------------------------+
//| Actualizar display en pantalla                                   |
//+------------------------------------------------------------------+
void UpdateDisplay()
{
   if(!ShowComment)
      return;

   string display = "SocketReceiver MT5\n";
   display += "Servidor: " + SocketHost + ":" + IntegerToString(SocketPort) + "\n";

   if(socketHandle == INVALID_HANDLE)
   {
      display += "Estado: DESCONECTADO\n";
      display += "Reintento cada: " + IntegerToString(ReconnectDelay) + "s\n";
   }
   else
   {
      display += "Estado: CONECTADO\n";
      display += "Mensajes: " + IntegerToString(messageCount) + "\n";
      if(StringLen(lastMessage) > 0)
      {
         display += "\nÚltimo mensaje:\n" + lastMessage + "\n";
      }
   }

   Comment(display);
}
