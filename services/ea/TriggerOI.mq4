//+------------------------------------------------------------------+
//|                                                   TriggerOI4.mq4 |
//|                                  Copyright 2025, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Panel de Botones Comprar / Vender / Cerrar (solo interfaz)       |
//| Pasos 1, 2 y 3 (sin lógica de trading)                           |
//+------------------------------------------------------------------+
#property strict
#include "..\\Libraries\\LibreriaTriggerOI.mq4"

//--- Nombres de los botones
#define BTN_BUY    "btn_buy"
#define BTN_SELL   "btn_sell"
#define BTN_CLOSE  "btn_close"

//--- Colores activos/inactivos
#define CLR_BUY_ACTIVE    clrGreen      // botón Comprar activo
#define CLR_BUY_INACTIVE  clrDarkGreen  // botón Comprar inactivo

#define CLR_SELL_ACTIVE   clrRed        // botón Vender activo
#define CLR_SELL_INACTIVE clrMaroon     // botón Vender inactivo

#define CLR_CLOSE_ACTIVE   clrDarkOrange // botón Cerrar activo (naranja oscuro)
#define CLR_CLOSE_INACTIVE clrDarkOrange // botón Cerrar inactivo (mismo fondo, texto gris)

//--- Estados lógicos de los botones
bool gBuyEnabled   = true;
bool gSellEnabled  = true;
bool gCloseEnabled = false;

//Estado actual direccion
int DireccionActual = DIR_NODIR;
int DireccionNueva = DIR_NODIR;
bool PrimeraIteracion = false;

//+------------------------------------------------------------------+
//| Función auxiliar: crear un botón en el chart                     |
//+------------------------------------------------------------------+
bool CreateButton(string name,
                  string text,
                  int xDistance,
                  int yDistance,
                  int xSize,
                  int ySize,
                  color backColor)
{
   // Si ya existe, lo borramos primero
   if(ObjectFind(0,name) >= 0)
      ObjectDelete(0,name);

   if(!ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0))
      return(false);

   ObjectSetInteger(0, name, OBJPROP_CORNER,   CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, xDistance);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, yDistance);
   ObjectSetInteger(0, name, OBJPROP_XSIZE,     xSize);
   ObjectSetInteger(0, name, OBJPROP_YSIZE,     ySize);

   ObjectSetString (0, name, OBJPROP_TEXT,  text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);        // color del texto
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, backColor);     // color de fondo
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 10);
   ObjectSetString (0, name, OBJPROP_FONT, "Arial");

   ObjectSetInteger(0, name, OBJPROP_BACK,        true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,  false);
   ObjectSetInteger(0, name, OBJPROP_SELECTED,    false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,      false);
   ObjectSetInteger(0, name, OBJPROP_STATE,       false);

   return(true);
}

//+------------------------------------------------------------------+
//| Función auxiliar: aplicar estilo según si el botón está activo   |
//+------------------------------------------------------------------+
void SetButtonEnabled(string name,
                      bool enabled,
                      color activeColor,
                      color inactiveColor)
{
   if(ObjectFind(0, name) < 0)
      return;

   // Fondo: color vivo si está activo, apagado si no
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR,
                    enabled ? activeColor : inactiveColor);

   // Texto: blanco si activo, gris si desactivado
   ObjectSetInteger(0, name, OBJPROP_COLOR,
                    enabled ? (color)clrWhite : (color)clrSilver);

   // Aseguramos que no quede en "modo pulsado"
   ObjectSetInteger(0, name, OBJPROP_STATE, false);
}

//+------------------------------------------------------------------+
//| Actualiza todos los botones según los flags globales             |
//+------------------------------------------------------------------+
void UpdateAllButtons()
{
   SetButtonEnabled(BTN_BUY,   gBuyEnabled,   CLR_BUY_ACTIVE,   CLR_BUY_INACTIVE);
   SetButtonEnabled(BTN_SELL,  gSellEnabled,  CLR_SELL_ACTIVE,  CLR_SELL_INACTIVE);
   SetButtonEnabled(BTN_CLOSE, gCloseEnabled, CLR_CLOSE_ACTIVE, CLR_CLOSE_INACTIVE);
}

//+------------------------------------------------------------------+
//| OnInit: crear botones y estado inicial                           |
//+------------------------------------------------------------------+
int OnInit()
{
   // Estado inicial
   gBuyEnabled   = true;
   gSellEnabled  = true;
   gCloseEnabled = false;

   // Crear botones (posición simple en la parte superior izquierda)
   int x0 = 10;
   int y0 = 20;
   int w  = 90;
   int h  = 20;

   CreateButton(BTN_BUY,   "Comprar", x0,          y0, w, h, CLR_BUY_ACTIVE);
   CreateButton(BTN_SELL,  "Vender",  x0 + 100,    y0, w, h, CLR_SELL_ACTIVE);
   CreateButton(BTN_CLOSE, "Cerrar",  x0 + 200,    y0, w, h, CLR_CLOSE_ACTIVE);

   // Ajustar colores según estados (Cerrar empezará apagado)
   UpdateAllButtons();

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit: limpiar los objetos del chart                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectDelete(0, BTN_BUY);
   ObjectDelete(0, BTN_SELL);
   ObjectDelete(0, BTN_CLOSE);
}

//+------------------------------------------------------------------+
//| OnTick: de momento vacío (sin lógica de trading)                 |
//+------------------------------------------------------------------+
void OnTick()
{

   if (LecturaMercado)
   { 
      Traza1 = "";
      if (Log == 1) Trazas(" LecturaMercado-->...", Traza1);      
      if (Log == 1) Traza2 = "";
      
      int Direccion = LecturaOnda();
      if (Log == 1) Trazas(" LecturaMercado--> Direccion: " + IntegerToString(Direccion), Traza1);      

      if (Direccion == DIR_LARGOS)
      {               
         if (Comprar() > 0)
         {
            LecturaMercado = false;
            SalidaMercado = true;
         }
      }
      else if (Direccion == DIR_CORTOS)
      {                  
         if (Vender() > 0)
         {
            LecturaMercado = false;
            SalidaMercado = true;
         }
      }   
   }
   else if (SalidaMercado)
   {
      if (Log == 1) Traza3 = "";
      if (Log == 1) Trazas(" SalidaMercado", Traza3); 
           
      if (SalidaporTPSL(commentSalida) == 0)
      {
         if (Log == 1) Trazas(" TP ejecutado", Traza3); 
         LecturaMercado = true;
         SalidaMercado = false; 
         // Meter datos de pipos ganados y ganancias obtenidas...        
         if (Log == 1) Trazas(" Datos resumen de la operación: ", Traza3); 
      }
   }
   
   Comment("\n", "\n", "\n", "\n", Traza0, 
   "\n--------------------------------", 
   Traza1, 
   "\n--------------------------------", 
   Traza2,
   "\n--------------------------------",
   Traza3,        
   "\n--------------------------------",
   Traza4);         

}

//+------------------------------------------------------------------+
//| OnChartEvent: detectar clics en los botones                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,
                  const long   &lparam,
                  const double &dparam,
                  const string &sparam)
{
   if(id != CHARTEVENT_OBJECT_CLICK)
      return;

   string name = sparam;

   // Botón COMPRAR
   if(name == BTN_BUY && gBuyEnabled)
   {
      Comprar();      
   }

   // Botón VENDER
   else if(name == BTN_SELL && gSellEnabled)
   {
      Vender();
   }

   // Botón CERRAR
   else if(name == BTN_CLOSE && gCloseEnabled)
   {
      Cerrar();
   }
}
//+------------------------------------------------------------------+

int LecturaOnda()
{
   int iLecturaOnda = DIR_NODIR;

   int dir_M15 = GetDireccionPorWPR(Par, PERIOD_M15, 4, 8, 16);
   if (Log == 1) Trazas(" LecturaMercado-->WPR´s 15: " + IntegerToString(dir_M15), Traza1);

   int dir_M5  = GetDireccionPorWPR(Par, PERIOD_M5, 12, 24, 48);
   if (Log == 1) Trazas(" LecturaMercado-->WPR´s 5: " + IntegerToString(dir_M5), Traza1);

   int dir_M1  = GetDireccionPorWPR(Par, PERIOD_M1, 60, 120, 240);
   if (Log == 1) Trazas(" LecturaMercado-->WPR´s 1: " + IntegerToString(dir_M1), Traza1);
   
   int stoM15 = GetDireccionPorEstocasticosM15();
   
   int BB_EMA_M30_H1 = GetDireccionBB_EMA_M30_H1();
   if (Log == 1) Trazas(" LecturaMercado-->BB_EMA_M30_H1: " + IntegerToString(BB_EMA_M30_H1), Traza1);

   if ((dir_M15 == DIR_LARGOS) && (dir_M5 == DIR_LARGOS) 
   && (dir_M1 == DIR_LARGOS) && (stoM15 == DIR_LARGOS) && (BB_EMA_M30_H1 == DIR_LARGOS))
   {
      if (Log == 1) Trazas(" LecturaMercado-->WPR´s Largos", Traza1);

      if (GetOnda(DIR_LARGOS, PERIOD_M15, 8, 5, 3, 4, R0M15, R1M15, R2M15, R3M15) == DIR_LARGOS)
      {
//         double R0M5 = 0;
//         double R1M5 = 0;
//         double R2M5 = 0;
//         double R3M5 = 0;

//         if (GetOnda(DIR_LARGOS, PERIOD_M5, 24, 5, 9, 4, R0M5, R1M5, R2M5, R3M5) == DIR_LARGOS)     
//         {
//            double R0M1 = 0;
//            double R1M1 = 0;
//            double R2M1 = 0;
//            double R3M1 = 0;

//            if (GetOnda(DIR_LARGOS, PERIOD_M1, 120, 5, 45, 4, R0M1, R1M1, R2M1, R3M1) == DIR_LARGOS)        
//            {
//               if ((R0M15 == R0M5) && (R0M5 == R0M1))
//               {
//                  if ((R1M15 == R1M5) && (R1M5 == R1M1))
//                  {
//                     if ((R2M15 == R2M5) && (R2M5 == R2M1))
//                     {
                        ZigZagFractal(Par, PERIOD_M15, 16, 5, 6, 2);
                        
                        double N0 = ZZAux[0];
                        double N1 = ZZAux[1];
                        
                        if (Log == 1) Trazas(" LecturaOnda--> N0:" + DoubleToString(N0) + 
                        " N1:" + DoubleToString(N1) + " R3: " + DoubleToString(R3M15), Traza1);     
                        
                        if ((N0 == R3M15) || (N1 == R3M15))
                        {
                           ZigZagFractal(Par, PERIOD_M30, 8, 5, 3, 1);
                           
                           double FractalM30 = ZZAux[0];
                           double DirFractalM30 = ZZAuxDirFractal[0];

                           if (Log == 1) Trazas(" LecturaOnda--> FractalM30: " + DoubleToString(FractalM30) + 
                           " DirFractalM30: " + DoubleToString(DirFractalM30), Traza1);     

                           ZigZagFractal(Par, PERIOD_H1, 4, 5, 3, 1);

                           double FractalH1 = ZZAux[0];
                           double DirFractalH1 = ZZAuxDirFractal[0];

                           if (Log == 1) Trazas(" LecturaOnda--> FractalH1: " + DoubleToString(FractalH1) + 
                           " DirFractalH1: " + DoubleToString(DirFractalH1), Traza1);     
                           
                           if ((FractalH1 == FractalM30) && (DirFractalM30 == DirFractalH1)
                           && (DirFractalM30 == FRACTAL_DN))
                           {
                              if (Log == 1) Trazas(" LecturaOnda--> Ondas Largos ALINEADAS", Traza1);     
                              iLecturaOnda = DIR_LARGOS; 
                           }
//                        }  
//                     }                  
//                  }
//               }
//            }
         }
      }
   }
   else if ((dir_M15 == DIR_CORTOS) && (dir_M5 == DIR_CORTOS) 
   && (dir_M1 == DIR_CORTOS) && (stoM15 == DIR_CORTOS) && (BB_EMA_M30_H1 == DIR_CORTOS))
   {
      if (Log == 1) Trazas(" LecturaMercado-->WPR´s Cortos", Traza1); 
      
      if (GetOnda(DIR_CORTOS, PERIOD_M15, 8, 5, 3, 4, R0M15, R1M15, R2M15, R3M15) == DIR_CORTOS) 
      {
//         double R0M5 = 0;
//         double R1M5 = 0;
//         double R2M5 = 0;
//         double R3M5 = 0;

//         if (GetOnda(DIR_CORTOS, PERIOD_M5, 24, 5, 9, 4, R0M5, R1M5, R2M5, R3M5) == DIR_CORTOS)
//         {
//            double R0M1 = 0;
//            double R1M1 = 0;
//            double R2M1 = 0;
//            double R3M1 = 0;
            
//            if (GetOnda(DIR_CORTOS, PERIOD_M1, 120, 5, 45, 4, R0M1, R1M1, R2M1, R3M1) == DIR_CORTOS) 
//            {
//               if ((R0M15 == R0M5) && (R0M5 == R0M1))
//               {
//                  if ((R1M15 == R1M5) && (R1M5 == R1M1))
//                  {
//                     if ((R2M15 == R2M5) && (R2M5 == R2M1))
//                     {
                        ZigZagFractal(Par, PERIOD_M15, 16, 5, 6, 2);
                        
                        double N0 = ZZAux[0];
                        double N1 = ZZAux[1];

                        if (Log == 1) Trazas(" LecturaOnda--> N0:" + DoubleToString(N0) + 
                        " N1:" + DoubleToString(N1) + " R3: " + DoubleToString(R3M15), Traza1);     
                        
                        if ((N0 == R3M15) || (N1 == R3M15))
                        {
                           ZigZagFractal(Par, PERIOD_M30, 8, 5, 3, 1);
                           
                           double FractalM30 = ZZAux[0];
                           double DirFractalM30 = ZZAuxDirFractal[0];

                           if (Log == 1) Trazas(" LecturaOnda--> FractalM30: " + DoubleToString(FractalM30) + 
                           " DirFractalM30: " + DoubleToString(DirFractalM30), Traza1);     

                           ZigZagFractal(Par, PERIOD_H1, 4, 5, 3, 1);

                           double FractalH1 = ZZAux[0];
                           double DirFractalH1 = ZZAuxDirFractal[0];

                           if (Log == 1) Trazas(" LecturaOnda--> FractalH1: " + DoubleToString(FractalH1) + 
                           " DirFractalH1: " + DoubleToString(DirFractalH1), Traza1);     
                           
                           if ((FractalH1 == FractalM30) && (DirFractalM30 == DirFractalH1)
                           && (DirFractalM30 == FRACTAL_UP))
                           {
                              if (Log == 1) Trazas(" LecturaOnda--> Ondas Cortos ALINEADAS", Traza1);     
                              iLecturaOnda = DIR_CORTOS;
                           } 
                        }  
//                     }                  
//                  }
//               }
//            }
//         } 
      } 
   }

   return(iLecturaOnda);  
}

int GetOnda(int Direccion, ENUM_TIMEFRAMES iPeriodo, int Depth, 
int Deviation, int Backstep, int Iteraciones, double &R0, double &R1, double &R2, double &R3)
{
   int iGetOnda = DIR_NODIR;
   
   ZigZagFractal(Par, iPeriodo, Depth, Deviation, Backstep, Iteraciones);
   
   if (Direccion == DIR_CORTOS)
   {      
      if (Log == 1) Trazas(" GetOnda -->Periodo: " + IntegerToString(iPeriodo) + " (" + IntegerToString(Depth) + ") ", Traza1);
      if (Log == 1) Trazas(" 0: " + DoubleToString(ZZAux[0]) + " 1: " + DoubleToString(ZZAuxFractal[1])
      + " 2: " + DoubleToString(ZZAuxFractal[2]) + " 3: " + DoubleToString(ZZAuxFractal[3]), Traza1);                     
      
      if ((ZZAux[0] < ZZAuxFractal[1]) && (ZZAuxFractal[1] > ZZAuxFractal[2])
      && (ZZAuxFractal[2] < ZZAuxFractal[3]) && (ZZAuxFractal[3] > ZZAuxFractal[1])
      && (ZZAuxFractal[3] > ZZAux[0]))
      {
         iGetOnda = DIR_CORTOS; 
         if (Log == 1) Trazas(" GetOnda -->(" + IntegerToString(Depth) + ") Onda3: Cortos", Traza1); 
         R0 = ZZAux[0];
         R1 = ZZAuxFractal[1];
         R2 = ZZAuxFractal[2];
         R3 = ZZAuxFractal[3];         
      }         
   }
   else if (Direccion == DIR_LARGOS)
   {      
      if (Log == 1) Trazas(" GetOnda -->Periodo: " + IntegerToString(iPeriodo) + " (" + IntegerToString(Depth) + ") ", Traza1);
      if (Log == 1) Trazas(" 0: " + DoubleToString(ZZAux[0]) + " 1: " + DoubleToString(ZZAuxFractal[1])
      + " 2: " + DoubleToString(ZZAuxFractal[2]) + " 3: " + DoubleToString(ZZAuxFractal[3]), Traza1);                     
      
      
      if ((ZZAux[0] > ZZAuxFractal[1]) && (ZZAuxFractal[1] < ZZAuxFractal[2])
      && (ZZAuxFractal[2] > ZZAuxFractal[3]) && (ZZAuxFractal[3] < ZZAuxFractal[1])
      && (ZZAuxFractal[3] < ZZAux[0]))
      {
         iGetOnda = DIR_LARGOS; 
         if (Log == 1) Trazas(" GetOnda -->(" + IntegerToString(Depth) + ") Onda3: Largos", Traza1);                     
         R0 = ZZAux[0];
         R1 = ZZAuxFractal[1];
         R2 = ZZAuxFractal[2];
         R3 = ZZAuxFractal[3];
      }
   }

   if (Log == 1) Trazas(" Salida GetOnda-->" + IntegerToString(iGetOnda), Traza1);       
   
   return (iGetOnda);
}

int Comprar()
{
   LotsForMarginPercent(0.7, numerooperaciones, miniLotes);

   commentSalida = Par;
   if (Log == 1) Trazas(" CommentSalida:" + commentSalida + " Nº Operaciones: " + IntegerToString(numerooperaciones) + " MiniLotes: " + DoubleToStr(miniLotes)  , Traza2);
   
   OperacionesAbiertas = ExecMarket(DIR_LARGOS, numerooperaciones, miniLotes, commentSalida, R1M15);
   if (Log == 1) Trazas(" Operaciones Abiertas: " + IntegerToString(OperacionesAbiertas), Traza2);

   //Ejecutas orden en el mercado
   if (OperacionesAbiertas > 0)
   {
      // Al comprar, desactivamos Comprar y Vender,
      // y dejamos solo Cerrar activo.
      gBuyEnabled   = false;
      gSellEnabled  = false;
      gCloseEnabled = true;

      UpdateAllButtons();
   }
   
   return(OperacionesAbiertas);
}

int Vender()
{
   // Al vender, desactivamos Comprar y Vender,
   // y dejamos solo Cerrar activo.
   LotsForMarginPercent(0.7, numerooperaciones, miniLotes);

   commentSalida = Par;
   if (Log == 1) Trazas(" CommentSalida:" + commentSalida + " Nº Operaciones: " + IntegerToString(numerooperaciones) + " MiniLotes: " + DoubleToStr(miniLotes), Traza2);
   
   OperacionesAbiertas = ExecMarket(DIR_CORTOS, numerooperaciones, miniLotes, commentSalida, R1M15);
   if (Log == 1) Trazas(" Operaciones Abiertas: " + IntegerToString(OperacionesAbiertas), Traza2);

   //Ejecutas orden en el mercado
   if (OperacionesAbiertas > 0)
   {
      gBuyEnabled   = false;
      gSellEnabled  = false;
      gCloseEnabled = true;

      UpdateAllButtons();
   }

   return(OperacionesAbiertas);

}

void Cerrar()
{
   if (CierreOrdenes(commentSalida) > 0)
   {
      if (Log == 1) Trazas(" Cerradas operaciones", Traza3);      
      // Volver al estado inicial
      gBuyEnabled   = true;
      gSellEnabled  = true;
      gCloseEnabled = false;
   
      UpdateAllButtons();
   }   
}